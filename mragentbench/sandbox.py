"""Start an agent process for mrab: always with a parent-death signal, optionally in a per-arm sandbox (Linux).

mrab runs this file as a script with the interpreter that runs mrab:

    python -I sandbox.py SPEC_JSON -- ARGV...

SPEC_JSON is a JSON object. Without "sandbox": true the launcher only asks the kernel to kill it when mrab dies
(PR_SET_PDEATHSIG, Linux) and then executes ARGV in place, so ARGV keeps the launcher's process id and process group.

With "sandbox": true it creates new user, mount and process-id namespaces (no privileges needed where the kernel allows
unprivileged user namespaces) and, inside them:

- gives the home folder ("home") a private copy-on-write view (overlayfs; upper and work folders under "home_upper"),
  so files that one arm's agent writes there (sessions, caches, notes) are invisible to the other arm and discarded
  after the run;
- mounts an empty tmpfs over every folder in "hide" (the runs folder, the instance data with graders and hidden data,
  every staging folder, the add-on source, /tmp, /var/tmp, /dev/shm), deepest first;
- mounts the arm's own workspace ("work") back at its path, read-write, and starts ARGV there as process 2 of the new
  process-id namespace, under a small init that is process 1 and exits with ARGV's status.

When the init process dies (for example because mrab killed the process group), the kernel kills every process left in
the namespace, so nothing the agent started can outlive the run. If any step fails, the launcher prints
"mrab-sandbox: setup failed: ..." on standard error and exits with status 125 before ARGV starts.

Standard library only and no imports from mragentbench, so the file also runs on its own (python -I).
"""

from __future__ import annotations

import ctypes
import json
import os
import signal
import sys

SETUP_FAILED = 125
CLONE_NEWNS = 0x00020000
CLONE_NEWUSER = 0x10000000
CLONE_NEWPID = 0x20000000
MS_NOSUID = 2
MS_NODEV = 4
MS_BIND = 4096
MS_REC = 16384
MS_PRIVATE = 1 << 18
PR_SET_PDEATHSIG = 1


def _libc() -> ctypes.CDLL | None:
    if not sys.platform.startswith("linux"):
        return None
    try:
        return ctypes.CDLL(None, use_errno=True)
    except OSError:
        return None


def set_parent_death_signal(libc: ctypes.CDLL | None) -> None:
    """Ask the kernel to send SIGKILL to this process when its parent dies (Linux only; no-op elsewhere)."""
    if libc is not None:
        libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)


def _mount(
    libc: ctypes.CDLL, source: str | None, target: str, fstype: str | None, flags: int, data: str | None
) -> None:
    def enc(s: str | None) -> bytes | None:
        return s.encode() if s is not None else None

    if libc.mount(enc(source), enc(target), enc(fstype), ctypes.c_ulong(flags), enc(data)) != 0:
        err = ctypes.get_errno()
        raise OSError(err, f"mount {fstype or source} on {target}: {os.strerror(err)}")


def _write(path: str, text: str) -> None:
    with open(path, "w") as f:
        f.write(text)


def _rebind(libc: ctypes.CDLL, fd: int, target: str) -> None:
    """Mount the folder open as fd at target (recursively), creating target inside a hiding tmpfs if needed."""
    os.makedirs(target, exist_ok=True)
    _mount(libc, f"/proc/self/fd/{fd}", target, None, MS_BIND | MS_REC, None)


def _setup_mounts(libc: ctypes.CDLL, spec: dict) -> None:
    """Runs as process 1 of the new namespaces, before the agent starts."""
    work = spec["work"]
    _mount(libc, None, "/", None, MS_REC | MS_PRIVATE, None)
    try:  # a fresh /proc shows only this namespace's processes; container runtimes may forbid it
        _mount(libc, "proc", "/proc", "proc", MS_NOSUID | MS_NODEV, None)
    except OSError:
        pass
    work_fd = os.open(work, os.O_PATH | os.O_DIRECTORY)
    home, home_fd = spec.get("home"), None
    if home:
        upper = spec["home_upper"]
        options = f"lowerdir={home},upperdir={upper}/upper,workdir={upper}/work,userxattr"
        _mount(libc, "overlay", home, "overlay", 0, options)
        home_fd = os.open(home, os.O_PATH | os.O_DIRECTORY)
    for path in sorted(spec.get("hide", []), key=lambda p: (-p.count("/"), p)):  # deepest first
        if os.path.isdir(path):
            _mount(libc, "tmpfs", path, "tmpfs", MS_NOSUID | MS_NODEV, "mode=0755")
    if home_fd is not None:
        _rebind(libc, home_fd, home)
    _rebind(libc, work_fd, work)
    os.close(work_fd)
    if home_fd is not None:
        os.close(home_fd)
    os.chdir(work)


def _init(libc: ctypes.CDLL, spec: dict, argv: list[str]) -> None:
    """Process 1 of the sandbox: set up the mounts, start the agent as process 2, wait, exit with its status."""
    set_parent_death_signal(libc)
    try:
        _setup_mounts(libc, spec)
    except OSError as e:
        print(f"mrab-sandbox: setup failed: {e}", file=sys.stderr, flush=True)
        os._exit(SETUP_FAILED)
    child = os.fork()
    if child == 0:
        try:
            os.execvp(argv[0], argv)
        except OSError as e:
            print(f"mrab-sandbox: cannot start {argv[0]}: {e}", file=sys.stderr, flush=True)
            os._exit(127)
    while True:
        try:
            pid, status = os.waitpid(-1, 0)
        except ChildProcessError:
            os._exit(1)
        if pid == child:
            os._exit(_exit_code(status))


def _exit_code(status: int) -> int:
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return os.WEXITSTATUS(status)


def run_sandboxed(spec: dict, argv: list[str]) -> None:
    """Create the namespaces, fork the init process and wait for it; never returns."""
    libc = _libc()
    if libc is None:
        print("mrab-sandbox: setup failed: the sandbox needs Linux", file=sys.stderr, flush=True)
        os._exit(SETUP_FAILED)
    set_parent_death_signal(libc)
    uid, gid = os.getuid(), os.getgid()
    try:
        if libc.unshare(CLONE_NEWUSER | CLONE_NEWNS | CLONE_NEWPID) != 0:
            err = ctypes.get_errno()
            raise OSError(err, f"unshare: {os.strerror(err)}")
        _write("/proc/self/setgroups", "deny")
        _write("/proc/self/uid_map", f"{uid} {uid} 1")
        _write("/proc/self/gid_map", f"{gid} {gid} 1")
    except OSError as e:
        print(f"mrab-sandbox: setup failed: {e}", file=sys.stderr, flush=True)
        os._exit(SETUP_FAILED)
    child = os.fork()
    if child == 0:
        _init(libc, spec, argv)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):  # stopping the launcher stops the whole sandbox
        signal.signal(sig, lambda *_: os.kill(child, signal.SIGKILL))
    while True:
        try:
            _, status = os.waitpid(child, 0)
            break
        except InterruptedError:
            continue
    code = _exit_code(status)
    if code > 128 and code - 128 in (signal.SIGKILL, signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(code - 128, signal.SIG_DFL)
        os.kill(os.getpid(), code - 128)
    os._exit(code)


def main(args: list[str]) -> None:
    if len(args) < 3 or args[1] != "--":
        print("usage: sandbox.py SPEC_JSON -- ARGV...", file=sys.stderr)
        os._exit(2)
    spec, argv = json.loads(args[0]), args[2:]
    if spec.get("sandbox"):
        run_sandboxed(spec, argv)
    set_parent_death_signal(_libc())
    try:
        os.execvp(argv[0], argv)
    except OSError as e:
        print(f"mrab: cannot start {argv[0]}: {e}", file=sys.stderr, flush=True)
        os._exit(127)


if __name__ == "__main__":
    main(sys.argv[1:])
