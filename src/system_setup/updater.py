"""
Self-update: the bootstrap clones the repo to ~/system-setup and installs it
with `uv tool install`. Updating = move that clone to the new version + reinstall.

Two channels (settings.ini, [general] updates = stable | latest):
  stable  (default)  only released versions: the newest vX.Y.Z tag
  latest             whatever is on master, tagged or not
"""
import os
import platform
import re
import shutil
import subprocess
import tempfile
from importlib.metadata import PackageNotFoundError, version

from . import settings
from .winenv import NO_WINDOW

IS_WINDOWS = platform.system() == "Windows"
REPO_DIR = os.path.join(os.path.expanduser("~"), "system-setup")
BRANCH = "master"
CHANNELS = ("stable", "latest")
_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def get_channel() -> str:
    ch = settings.get("updates", "stable")
    return ch if ch in CHANNELS else "stable"


def set_channel(channel: str) -> None:
    if channel not in CHANNELS:
        raise ValueError(f"Unknown update channel: {channel}")
    settings.set("updates", channel)


def _git(*args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", REPO_DIR, *args],
        capture_output=True, text=True, timeout=timeout,
        stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
    )


def _installed_version() -> tuple[int, int, int] | None:
    try:
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)", version("system-setup"))
        return tuple(map(int, m.groups())) if m else None
    except PackageNotFoundError:
        return None


def _newest_tag() -> tuple[str, tuple[int, int, int]] | None:
    tags = []
    for name in _git("tag", "--list", "v*").stdout.split():
        m = _TAG.match(name)
        if m:
            tags.append((tuple(map(int, m.groups())), name))
    if not tags:
        return None
    ver, name = max(tags)
    return name, ver


def check(channel: str | None = None) -> str | None:
    """
    The version we'd update to ("v0.3.0", or "master abc1234" on the latest
    channel), or None when there's nothing newer.

    stable: the newest vX.Y.Z tag, if its version is higher than the installed
            one, or the same version but we're on an untagged build of it
            (e.g. switched over from the latest channel).
    latest: origin/master, if it has commits we don't and we can fast-forward
            (local-only commits in the clone don't count as an update).
    """
    channel = channel or get_channel()
    if not os.path.exists(os.path.join(REPO_DIR, ".git")):
        return None
    try:
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", REPO_DIR],
            capture_output=True, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
        _git("fetch", "origin", "--tags", "--force", "--quiet", timeout=30)
        head = _git("rev-parse", "HEAD").stdout.strip()
        if not head:
            return None
        if channel == "latest":
            remote = _git("rev-parse", f"origin/{BRANCH}").stdout.strip()
            if not remote or remote == head:
                return None
            if _git("merge-base", "--is-ancestor", "HEAD", f"origin/{BRANCH}").returncode != 0:
                return None
            return f"{BRANCH} {remote[:7]}"
        newest = _newest_tag()
        if not newest:
            return None
        name, ver = newest
        installed = _installed_version()
        if installed is None or ver > installed:
            return name
        if ver == installed and _git("rev-parse", f"{name}^{{commit}}").stdout.strip() != head:
            return name
        return None
    except Exception:
        return None


def update_available() -> bool:
    return check() is not None


def pull(channel: str | None = None) -> tuple[bool, str]:
    """Move the clone to the update check() found. Doesn't reinstall."""
    channel = channel or get_channel()
    target = check(channel)
    if not target:
        return False, "No update found."
    # The clone is ours, not a workspace: --force so a stray file (e.g. a uv.lock
    # that uv generated before the repo tracked one) can't block the switch.
    if channel == "latest":
        # check() already confirmed origin/master is a fast-forward of HEAD
        r = _git("checkout", "--quiet", "--force", "-B", BRANCH, f"origin/{BRANCH}", timeout=60)
    else:
        r = _git("-c", "advice.detachedHead=false", "checkout", "--quiet", "--force", "--detach", target, timeout=60)
    return r.returncode == 0, "\n".join([target, r.stdout.strip(), r.stderr.strip()]).strip()


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
