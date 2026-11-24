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


def elevation_type() -> str:
    """
    'full'    — admin account, this process is elevated
    'limited' — admin account, this process is NOT elevated (normal UAC state)
    'default' — standard account (or UAC disabled)
    """
    if not IS_WINDOWS:
        return "full" if is_admin() else "default"
    try:
        import ctypes
        from ctypes import wintypes
        adv, k32 = ctypes.windll.advapi32, ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        token = wintypes.HANDLE()
        if not adv.OpenProcessToken(k32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
            return "default"
        try:
            value, size = ctypes.c_int(), wintypes.DWORD()
            if not adv.GetTokenInformation(token, 18, ctypes.byref(value), 4, ctypes.byref(size)):  # TokenElevationType
                return "default"
            return {2: "full", 3: "limited"}.get(value.value, "default")
        finally:
            k32.CloseHandle(token)
    except Exception:
        return "default"


def is_admin_account() -> bool:
    """True if UAC elevation keeps the same user (so profile paths stay the same)."""
    return is_admin() or elevation_type() in ("full", "limited")


def _pythonw() -> str:
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return pyw if os.path.exists(pyw) else exe


def relaunch_elevated(module: str, extra_args: list[str] | None = None) -> bool:
    """
    Start `python -m <module>` elevated via UAC. Returns True if the elevated
    process was launched (caller should then exit), False if the user declined.
    """
    if not IS_WINDOWS:
        return False
    import ctypes
    args = subprocess.list2cmdline(["-m", module] + (extra_args or []))
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", _pythonw(), args, None, 1)
    return rc > 32


class ElevationCancelled(Exception):
    pass


def start_elevated_helper(spec_path: str):
    """
    Launch `pythonw -m system_setup.elevated <spec_path>` through UAC and return
    a process handle (for wait_handle). Raises ElevationCancelled if the user
    says no. On a standard account, UAC asks for an administrator's password.
    """
    import ctypes
    from ctypes import wintypes

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE),
        ]

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040 | 0x00000400        # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI
    info.lpVerb = "runas"
    info.lpFile = _pythonw()
    info.lpParameters = subprocess.list2cmdline(["-m", "system_setup.elevated", spec_path])
    info.nShow = 0                              # SW_HIDE
    shell32 = ctypes.windll.shell32
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    if not shell32.ShellExecuteExW(ctypes.byref(info)) or not info.hProcess:
        raise ElevationCancelled()
    return info.hProcess


def wait_handle(handle, timeout_ms: int) -> int | None:
    """Exit code if the process has finished within timeout_ms, else None."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    if k32.WaitForSingleObject(handle, timeout_ms) != 0:   # WAIT_OBJECT_0
        return None
    code = wintypes.DWORD()
    k32.GetExitCodeProcess(handle, ctypes.byref(code))
    k32.CloseHandle(handle)
    return code.value
