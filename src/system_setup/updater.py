"""
Self-update: the bootstrap clones the repo to ~/system-setup and installs it
with `uv tool install`. Updating = git pull + reinstall from that clone.
"""
import os
import platform
import shutil
import subprocess
import tempfile

from .winenv import NO_WINDOW

IS_WINDOWS = platform.system() == "Windows"
REPO_DIR = os.path.join(os.path.expanduser("~"), "system-setup")
BRANCH = "origin/master"


def _git(*args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", REPO_DIR, *args],
        capture_output=True, text=True, timeout=timeout,
        stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
    )


def update_available() -> bool:
    """
    True only when origin/master has commits we don't have AND we can
    fast-forward to it (i.e. HEAD is an ancestor). Local-only commits in the
    clone don't count as an 'update'.
    """
    if not os.path.exists(os.path.join(REPO_DIR, ".git")):
        return False
    try:
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", REPO_DIR],
            capture_output=True, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
        _git("fetch", "origin", "--quiet")
        local = _git("rev-parse", "HEAD").stdout.strip()
        remote = _git("rev-parse", BRANCH).stdout.strip()
        if not local or not remote or local == remote:
            return False
        return _git("merge-base", "--is-ancestor", "HEAD", BRANCH).returncode == 0
    except Exception:
        return False


def pull() -> tuple[bool, str]:
    r = _git("pull", "--ff-only", timeout=60)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def schedule_reinstall(relaunch: str | None = None) -> None:
    """
    Reinstall the uv tool from REPO_DIR. On Windows the running .exe is locked,
    so a detached batch file waits for us to exit, reinstalls, then optionally
    relaunches `relaunch` (a command name like 'system-setupg').
    """
    uv_exe = shutil.which("uv") or "uv"
    if not IS_WINDOWS:
        subprocess.run([uv_exe, "tool", "install", REPO_DIR, "--reinstall"], check=False)
        return
    relaunch_line = ""
    if relaunch:
        exe = shutil.which(relaunch) or os.path.join(os.path.expanduser("~"), ".local", "bin", relaunch + ".exe")
        relaunch_line = f'start "" "{exe}"\n'
    tmp = tempfile.NamedTemporaryFile(suffix=".cmd", delete=False, mode="w")
    # Note: `timeout` fails instantly in a detached process (it needs a console),
    # so use ping as the delay, and retry while our exe is still locked.
    tmp.write(
        "@echo off\n"
        "set n=0\n"
        ":retry\n"
        "ping -n 3 127.0.0.1 >nul\n"
        f'"{uv_exe}" tool install "{REPO_DIR}" --reinstall && goto done\n'
        "set /a n+=1\n"
        "if %n% lss 10 goto retry\n"
        ":done\n"
        f"{relaunch_line}"
        'del "%~f0"\n'
    )
    tmp.close()
    subprocess.Popen(
        ["cmd", "/c", tmp.name],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | NO_WINDOW,
        close_fds=True,
    )
