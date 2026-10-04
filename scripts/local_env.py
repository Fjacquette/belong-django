#!/usr/bin/env python3
"""Manage isolated local development and committed browser-test previews."""

import argparse
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from belong.environment import CONFIG_KEYS, read_local_config
from scripts import browser_server


def run(args, root, **kwargs):
    return subprocess.run(args, cwd=root, check=True, **kwargs)


def git_output(root, *args):
    return run(["git", *args], root, capture_output=True, text=True).stdout.strip()


def test_checkout(root):
    return root / ".worktrees" / "test"


def verify_test_checkout(root):
    checkout = test_checkout(root)
    if not (checkout / ".git").is_file():
        raise ValueError("Run ./scripts/refresh-test.sh to create the test worktree first.")
    if Path(git_output(checkout, "rev-parse", "--show-toplevel")) != checkout.resolve():
        raise ValueError("Test path is not a separate Git worktree.")
    common_dir = (checkout / git_output(checkout, "rev-parse", "--git-common-dir")).resolve()
    if common_dir != Path(git_output(root, "rev-parse", "--absolute-git-dir")).resolve():
        raise ValueError("Test worktree does not belong to this repository.")
    branch = git_output(checkout, "branch", "--show-current")
    if branch not in ("", "browser-test"):
        raise ValueError("Test worktree must use browser-test or a detached preview commit.")
    if not branch:
        preview = browser_server.read_state(browser_server.runtime(root) / "preview.json")
        head = git_output(checkout, "rev-parse", "HEAD")
        if (not isinstance(preview, dict) or preview.get("commit") != head) and not git_output(checkout, "for-each-ref", "--format=%(refname)", "--contains", head, "refs/heads/"):
            raise ValueError("Detached test checkout has local commits. Preserve them before continuing.")
    if git_output(checkout, "status", "--porcelain"):
        raise ValueError("Test worktree has source changes. Preserve or commit them before continuing.")
    return checkout


def initialize_local_config(checkout, environment):
    defaults = (
        f"BELONG_ENV={environment}\n"
        "DJANGO_DEBUG=true\n"
        "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1]\n"
        "DJANGO_DB_PATH=db.sqlite3\n"
    )
    for path, value in (
        (checkout / ".env.local", defaults),
        (checkout / ".django-secret-key", secrets.token_urlsafe(50) + "\n"),
    ):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(descriptor, "w") as handle:
            handle.write(value)


def local_environment(checkout, environment):
    config = read_local_config(checkout / ".env.local")
    if config.get("BELONG_ENV") != environment:
        raise ValueError(f"{checkout}/.env.local must set BELONG_ENV={environment}.")
    # Shell exports from dev must not accidentally make test use dev's database/key.
    env = {key: value for key, value in os.environ.items() if key not in CONFIG_KEYS}
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    env.update(config)
    env["DJANGO_SETTINGS_MODULE"] = "belong.settings"
    return env


def database_path(checkout, env):
    return (checkout / Path(env.get("DJANGO_DB_PATH", "db.sqlite3")).expanduser()).resolve()


def ensure_test_checkout(root, commit=None):
    checkout = test_checkout(root)
    if not checkout.exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        if commit:
            run(["git", "worktree", "add", "--detach", str(checkout), commit], root)
        elif git_output(root, "branch", "--list", "browser-test"):
            run(["git", "worktree", "add", str(checkout), "browser-test"], root)
        else:
            run(["git", "worktree", "add", "--track", "-b", "browser-test", str(checkout), "origin/master"], root)
    return verify_test_checkout(root)


def refresh_test(root):
    with browser_server.operation(root):
        run(["git", "fetch", "origin", "master"], root)
        checkout = ensure_test_checkout(root)
        # Preserve branch commits even when a detached preview is active.
        if git_output(root, "branch", "--list", "browser-test"):
            if git_output(checkout, "rev-list", "origin/master..browser-test"):
                raise ValueError("Test branch has local commits. Preserve them before refreshing; no reset was performed.")
        running = browser_server.stop(root, checkout)
        browser_server.require_free_port()
        if git_output(root, "branch", "--list", "browser-test"):
            run(["git", "switch", "--no-overwrite-ignore", "browser-test"], checkout)
        else:
            run(["git", "switch", "--no-overwrite-ignore", "--track", "-c", "browser-test", "origin/master"], checkout)
        run(["git", "merge", "--ff-only", "--no-overwrite-ignore", "origin/master"], checkout)
        initialize_local_config(checkout, "test")
        commit = git_output(checkout, "rev-parse", "HEAD")
        if running:
            env, _ = prepare(root, checkout, "test")
            browser_server.launch(root, checkout, env, commit)
        else:
            print(f"Browser-test now uses master at {commit[:7]}. Start it with ./start_test.sh.", flush=True)


def present_test(root):
    if git_output(root, "status", "--porcelain"):
        raise ValueError("Main worktree has uncommitted source changes; commit the iteration before presenting it.")
    commit = git_output(root, "rev-parse", "HEAD")
    with browser_server.operation(root):
        checkout = ensure_test_checkout(root, commit)
        browser_server.stop(root, checkout)
        browser_server.require_free_port()
        run(["git", "switch", "--no-overwrite-ignore", "--detach", commit], checkout)
        browser_server.write_state(browser_server.runtime(root) / "preview.json", {"commit": commit})
        env, _ = prepare(root, checkout, "test")
        browser_server.launch(root, checkout, env, commit)


def prepare(root, checkout, environment):
    initialize_local_config(checkout, environment)
    env = local_environment(checkout, environment)
    database = database_path(checkout, env)
    other = root if environment == "test" else test_checkout(root)
    if other.exists():
        other_config = read_local_config(other / ".env.local")
        if database == database_path(other, other_config):
            raise ValueError("Dev and browser-test must use separate database files.")
    database.parent.mkdir(parents=True, exist_ok=True)
    run(["uv", "sync", "--locked"], checkout, env=env)
    python = str(checkout / ".venv" / "bin" / "python")
    run([python, "manage.py", "check"], checkout, env=env)
    run([python, "manage.py", "migrate", "--noinput"], checkout, env=env)
    return env, database


def start(root, environment):
    if environment == "test":
        with browser_server.operation(root):
            checkout = verify_test_checkout(root)
            browser_server.stop(root, checkout)
            browser_server.require_free_port()
            env, _ = prepare(root, checkout, "test")
            browser_server.launch(root, checkout, env, git_output(checkout, "rev-parse", "HEAD"))
        return
    checkout = root
    env, database = prepare(root, checkout, environment)
    python = str(checkout / ".venv" / "bin" / "python")
    port = 8000
    print(f"{environment}: http://127.0.0.1:{port} | database: {database}", flush=True)
    watcher = None
    try:
        if environment == "dev":
            tailwind = [
                "npx", "tailwindcss@3.4.13", "-i", "assets/tailwind.css",
                "-o", "static/css/tailwind.css", "--minify",
            ]
            run(tailwind, checkout, env=env)
            watcher = subprocess.Popen(
                [*tailwind, "--watch"], cwd=checkout, env=env, start_new_session=True
            )
        # Browser-test uses master's committed CSS; dev watches its own source.
        command = [python, "manage.py", "runserver", f"127.0.0.1:{port}"]
        run(command, checkout, env=env)
    finally:
        if watcher is not None:
            try:
                os.killpg(watcher.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            watcher.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start-dev", "start-test", "refresh-test", "present-test", "stop-test"])
    command = parser.parse_args().command
    try:
        if command == "refresh-test":
            refresh_test(ROOT)
        elif command == "present-test":
            present_test(ROOT)
        elif command == "stop-test":
            with browser_server.operation(ROOT):
                stopped = browser_server.stop(ROOT, test_checkout(ROOT))
                print("Stopped managed browser-test." if stopped else "No managed browser-test server running.")
        else:
            start(ROOT, "dev" if command == "start-dev" else "test")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Local environment: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
