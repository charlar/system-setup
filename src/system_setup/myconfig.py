"""
MySQL saved logins: [client<suffix>] groups in an option file, used with
    mysql --defaults-group-suffix=<suffix>

On Linux, ~/.my.cnf is read by the mysql client automatically.
On Windows the client never reads a per-user option file, so our `mysql`
wrapper adds --defaults-extra-file=<this file> for you.
"""
import glob
import os
import platform
import re
import shutil
import subprocess

from .inifile import IniFile
from .winenv import NO_WINDOW

IS_WINDOWS = platform.system() == "Windows"

LOGIN_KEYS = ("host", "port", "user", "database")


def option_file() -> str:
    # Same location the original CLI used, so existing configs keep working
    if IS_WINDOWS:
        return os.path.join(os.path.expanduser("~"), "my.cnf")
    return os.path.expanduser("~/.my.cnf")


def _quote(v: str) -> str:
    # Option-file values: '#' starts a comment unless quoted; '\' is an escape.
    v = v.replace("\\", "\\\\")
    if '"' not in v:
        return f'"{v}"'
    if "'" not in v:
        return f"'{v}'"
    raise ValueError("Password can't contain both ' and \" characters")


def _unquote(v: str) -> str:
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1]
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "s": " "}.get(m.group(1), m.group(1)), v)


def list_logins() -> list[dict]:
    ini = IniFile(option_file())
    out = []
    for group in ini.names():
        if not group.startswith("client"):
            continue
        vals = ini.get(group) or {}
        pw = vals.get("password")
        out.append({
            "name": group[len("client"):],
            "group": group,
            **{k: vals.get(k, "") for k in LOGIN_KEYS},
            "has_password": pw is not None,
            "password": _unquote(pw) if pw is not None else "",
        })
    return out


def save_login(data: dict, old_name: str | None = None) -> None:
    name = (data.get("name") or "").strip()
    if any(c in name for c in "[]= \n"):
        raise ValueError("Name can't contain spaces or [ ] =")
    vals = {k: (data.get(k) or "").strip() for k in LOGIN_KEYS}
    if not vals["user"]:
        raise ValueError("User is required")
    if data.get("password") is not None:
        vals["password"] = _quote(data["password"]) if data["password"] else ""
    ini = IniFile(option_file())
    ini.set(f"client{name}", vals, old_name=f"client{old_name}" if old_name is not None else None)
    ini.save(private=True)


def delete_login(name: str) -> None:
    ini = IniFile(option_file())
    if ini.remove(f"client{name}"):
        ini.save(private=True)


def _version_key(path: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", path)]


def find_mysql() -> str | None:
    if IS_WINDOWS:
        matches = glob.glob(r"C:\Program Files\MySQL\*\bin\mysql.exe") + \
                  glob.glob(r"C:\tools\mysql\*\bin\mysql.exe")
        if matches:
            return max(matches, key=_version_key)
    return shutil.which("mysql")


def client_args(suffix: str) -> list[str]:
    """Option-file args that make the real mysql binary use our saved login."""
    args = []
    if IS_WINDOWS and os.path.exists(option_file()):
        args.append(f"--defaults-extra-file={option_file()}")   # must come first
    if suffix:
        args.append(f"--defaults-group-suffix={suffix}")
    return args


def test_login(name: str) -> tuple[bool, str]:
    mysql = find_mysql()
    if not mysql:
        return False, "mysql not found — install MySQL first."
    try:
        r = subprocess.run(
            [mysql, *client_args(name), "--connect-timeout=5", "-N", "-e", "select version()"],
            capture_output=True, text=True, timeout=20,
            stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return False, "Timed out."
    return r.returncode == 0, (r.stdout + r.stderr).strip()
