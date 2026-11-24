"""
Windows environment helpers: PATH refresh, admin detection, elevation.
All functions are safe no-ops (or return False) on non-Windows platforms.
"""
import os
import platform
import subprocess
import sys

IS_WINDOWS = platform.system() == "Windows"

# Flag to keep child console programs (choco, wsl, git...) from flashing a window
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _reg_path(root, subkey: str) -> str:
    import winreg
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _ = winreg.QueryValueEx(key, "Path")
            return value
    except OSError:
        return ""


def refresh_path() -> None:
    """
    Re-read machine + user PATH from the registry into this process.

    Installers (choco, MSI) update PATH in the registry, but a running process
    keeps its old copy — that's why a fresh install 'isn't found' until you open
    a new terminal. Entries already in our PATH are kept (in front) so anything
    we prepended at runtime survives.
    """
    if not IS_WINDOWS:
        return
    import winreg
    machine = _reg_path(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
    )
    user = _reg_path(winreg.HKEY_CURRENT_USER, "Environment")
    current = os.environ.get("PATH", "")

    seen: set[str] = set()
    merged: list[str] = []
    for entry in (current + ";" + machine + ";" + user).split(";"):
        entry = os.path.expandvars(entry.strip())
        key = entry.rstrip("\\").lower()
        if entry and key not in seen:
            seen.add(key)
            merged.append(entry)
    os.environ["PATH"] = ";".join(merged)


def is_admin() -> bool:
    if not IS_WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_elevated(module: str, extra_args: list[str] | None = None) -> bool:
    """
    Start `python -m <module>` elevated via UAC. Returns True if the elevated
    process was launched (caller should then exit), False if the user declined.
    """
    if not IS_WINDOWS:
        return False
    import ctypes
    exe = sys.executable
    # Prefer pythonw.exe so the elevated GUI doesn't get a console window
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    args = subprocess.list2cmdline(["-m", module] + (extra_args or []))
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
    return rc > 32
