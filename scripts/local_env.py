#!/usr/bin/env python3
"""Launch local environments and fast-forward the persistent browser-test checkout."""

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
    if git_output(checkout, "branch", "--show-current") != "browser-test":
        raise ValueError("Test worktree must stay on the browser-test branch.")
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


def refresh_test(root):
    run(["git", "fetch", "origin", "master"], root)
    checkout = test_checkout(root)
    if not checkout.exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run(
            ["git", "worktree", "add", "--track", "-b", "browser-test", str(checkout), "origin/master"],
            root,
        )
    checkout = verify_test_checkout(root)
    # Refuse local commits, including commits that happen to contain remote master.
    if git_output(checkout, "rev-list", "origin/master..HEAD"):
        raise ValueError("Test branch has local commits. Preserve them before refreshing; no reset was performed.")
    run(["git", "merge", "--ff-only", "--no-overwrite-ignore", "origin/master"], checkout)
    initialize_local_config(checkout, "test")
    print(f"Browser-test now uses master at {git_output(checkout, 'rev-parse', '--short', 'HEAD')}.", flush=True)
    print("Start it with ./start_test.sh. Its database and configuration were preserved.", flush=True)


def start(root, environment):
    checkout = root if environment == "dev" else verify_test_checkout(root)
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
    port = 8000 if environment == "dev" else 8001
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
        if environment == "test":
            command.append("--noreload")
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
    parser.add_argument("command", choices=["start-dev", "start-test", "refresh-test"])
    command = parser.parse_args().command
    try:
        if command == "refresh-test":
            refresh_test(ROOT)
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
