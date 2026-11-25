"""
Start-menu shortcut for system-setupg ("System Setup").

Created by both system-setup and system-setupg at startup if it's missing,
so people who only ever self-update (and never re-run the bootstrap) get it too.
  %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\System Setup.lnk
"""
import os
import shutil
import subprocess

from .winenv import IS_WINDOWS, NO_WINDOW

NAME = "System Setup"


def shortcut_path() -> str:
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                        "Microsoft", "Windows", "Start Menu", "Programs", f"{NAME}.lnk")


def gui_exe() -> str | None:
    """The installed system-setupg.exe — never a development .venv copy."""
    candidates = [
        os.path.join(os.environ["UV_TOOL_BIN_DIR"], "system-setupg.exe") if os.environ.get("UV_TOOL_BIN_DIR") else "",
        os.path.join(os.path.expanduser("~"), ".local", "bin", "system-setupg.exe"),
        shutil.which("system-setupg") or "",
    ]
    for c in candidates:
        if c and os.path.exists(c) and ".venv" not in c.lower().split(os.sep):
            return c
    return None


def ensure_shortcut(force: bool = False) -> bool:
    """Create the shortcut if missing. Never raises — a missing shortcut isn't worth a crash."""
    if not IS_WINDOWS:
        return False
    path = shortcut_path()
    if os.path.exists(path) and not force:
        return True
    target = gui_exe()
    if not target:
        return False
    q = lambda s: "'" + s.replace("'", "''") + "'"     # PowerShell single-quoted string
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({q(path)}); "
        f"$s.TargetPath = {q(target)}; "
        f"$s.WorkingDirectory = {q(os.path.expanduser('~'))}; "
        f"$s.Description = {q('Install tools and manage saved connections / Instalar herramientas y conexiones')}; "
        "$s.Save()"
    )
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, timeout=30, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return os.path.exists(path)
