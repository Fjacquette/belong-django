"""Linux-only ownership and readiness checks for the local browser-test server."""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ADDRESS = ("127.0.0.1", 8001)
URL = "http://127.0.0.1:8001"


def runtime(root):
    path = root / ".belong-runtime"
    path.mkdir(mode=0o700, exist_ok=True)
    return path


@contextmanager
def operation(root):
    with (runtime(root) / "browser-test.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another browser-test operation is running.") from None
        yield


def write_state(path, value):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as handle:
        os.chmod(temporary, 0o600)
        json.dump(value, handle)
    temporary.replace(path)


def read_state(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return None


def identity(pid):
    """A PID alone is insufficient: check start time, command, and checkout too."""
    try:
        proc = Path("/proc") / str(pid)
        fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {
            "pid": pid,
            "started": fields[19],
            "command": (proc / "cmdline").read_bytes().decode().rstrip("\0").split("\0"),
            "checkout": str((proc / "cwd").resolve(strict=True)),
        }
    except (OSError, IndexError, UnicodeError):
        return None


def command(checkout):
    return [str(checkout / ".venv/bin/python"), "manage.py", "runserver", "127.0.0.1:8001", "--noreload"]


def owned(state, checkout):
    if not isinstance(state, dict) or not isinstance(state.get("pid"), int):
        return False
    current = identity(state["pid"])
    return bool(current and current == state.get("identity")
                and current["checkout"] == str(checkout.resolve())
                and current["command"] == command(checkout.resolve()))


def alive(state):
    # During exit cmdline/cwd can disappear before the listening socket closes.
    try:
        fields = (Path("/proc") / str(state["pid"]) / "stat").read_text().rsplit(")", 1)[1].split()
        return fields[0] != "Z" and fields[19] == state["identity"]["started"]
    except (OSError, IndexError):
        return False


def stop(root, checkout):
    path = runtime(root) / "browser-test.json"
    state = read_state(path)
    if not owned(state, checkout):
        path.unlink(missing_ok=True)
        return False
    # Pin the process so even a PID reuse between checking and signalling is safe.
    try:
        descriptor = os.pidfd_open(state["pid"])
    except ProcessLookupError:
        path.unlink(missing_ok=True)
        return False
    try:
        if not owned(state, checkout):
            path.unlink(missing_ok=True)
            return False
        try:
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 5
        while alive(state) and time.monotonic() < deadline:
            time.sleep(0.05)
        if owned(state, checkout):
            try:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 2
            while alive(state) and time.monotonic() < deadline:
                time.sleep(0.05)
        if alive(state):
            raise ValueError("Managed browser-test server did not stop.")
    finally:
        os.close(descriptor)
    path.unlink(missing_ok=True)
    return True


def require_free_port():
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(ADDRESS)
        except OSError:
            raise ValueError("Port 8001 is occupied by an unknown process; it was not killed.") from None


def serves_port(pid):
    """Readiness must belong to our process, not a racing unrelated listener."""
    try:
        inodes = {
            line.split()[9]
            for line in Path("/proc/net/tcp").read_text().splitlines()[1:]
            if line.split()[1] == f"0100007F:{ADDRESS[1]:04X}" and line.split()[3] == "0A"
        }
        return any(os.readlink(fd) in {f"socket:[{inode}]" for inode in inodes}
                   for fd in (Path("/proc") / str(pid) / "fd").iterdir())
    except OSError:
        return False


def launch(root, checkout, env, commit, timeout=20):
    require_free_port()
    path = runtime(root) / "browser-test.json"
    log = runtime(root) / "browser-test.log"
    with log.open("ab") as output:
        process = subprocess.Popen(command(checkout), cwd=checkout, env=env,
                                   stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                   start_new_session=True, close_fds=True)
    state = {"pid": process.pid, "identity": identity(process.pid), "commit": commit}
    try:
        write_state(path, state)
        opener = build_opener(ProxyHandler({}))  # Readiness is always a direct localhost request.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError(f"Browser-test exited during startup. See {log}.")
            if owned(state, checkout) and serves_port(process.pid):
                try:
                    with opener.open(URL + "/accounts/login/", timeout=1) as response:
                        if response.status == 200:
                            print(f"Browser-test ready at {URL} — {commit[:7]}", flush=True)
                            return
                except (OSError, URLError):
                    pass
            time.sleep(0.1)
        raise ValueError(f"Browser-test did not become ready. See {log}.")
    except BaseException:
        # This child is ours even if it exited before /proc identity was captured.
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        path.unlink(missing_ok=True)
        raise
