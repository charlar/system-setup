"""
PostgreSQL connection services: pg_service.conf (connection details) +
pgpass (passwords). A "service" is what you use with:  psql service=<name>

  Windows: %APPDATA%\\postgresql\\.pg_service.conf  and  %APPDATA%\\postgresql\\pgpass.conf
  Linux:   ~/.pg_service.conf                     and  ~/.pgpass
  (PGSERVICEFILE / PGPASSFILE environment variables override both.)
"""
import glob
import os
import platform
import re
import shutil
import subprocess

from .i18n import t
from .inifile import IniFile
from .winenv import NO_WINDOW

IS_WINDOWS = platform.system() == "Windows"

SERVICE_KEYS = ("host", "port", "dbname", "user")


def service_file() -> str:
    if os.environ.get("PGSERVICEFILE"):
        return os.environ["PGSERVICEFILE"]
    if IS_WINDOWS:
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "postgresql", ".pg_service.conf")
    return os.path.expanduser("~/.pg_service.conf")


def pgpass_file() -> str:
    if os.environ.get("PGPASSFILE"):
        return os.environ["PGPASSFILE"]
    if IS_WINDOWS:
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "postgresql", "pgpass.conf")
    return os.path.expanduser("~/.pgpass")


# ---------------------------------------------------------------------------
# pgpass parsing — fields are host:port:db:user:password, with \: and \\ escapes
# ---------------------------------------------------------------------------

def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace(":", "\\:")


def _split_pgpass(line: str) -> list[str] | None:
    s = line.rstrip("\r\n")
    if not s.strip() or s.lstrip().startswith("#"):
        return None
    fields, cur, i = [], [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            cur.append(s[i + 1])
            i += 2
            continue
        if c == ":" and len(fields) < 4:
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    fields.append("".join(cur))
    return fields if len(fields) == 5 else None


def _read_pgpass() -> list[str]:
    try:
        with open(pgpass_file(), encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def _write_pgpass(lines: list[str]) -> None:
    path = pgpass_file()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    if not IS_WINDOWS:
        os.chmod(path, 0o600)


def _key(svc: dict) -> tuple[str, str, str, str]:
    user = svc.get("user") or "postgres"
    return (
        svc.get("host") or "localhost",
        svc.get("port") or "5432",
        svc.get("dbname") or user,
        user,
    )


def lookup_password(svc: dict) -> str | None:
    """First matching pgpass line wins, '*' matches anything — same as libpq."""
    want = _key(svc)
    for line in _read_pgpass():
        f = _split_pgpass(line)
        if f and all(a == "*" or a == b for a, b in zip(f[:4], want)):
            return f[4]
    return None


def _set_password(svc: dict, password: str) -> None:
    want = _key(svc)
    lines = [l for l in _read_pgpass() if (_split_pgpass(l) or [None])[:4] != list(want)]
    # Put it first so it wins over any wildcard entries further down
    lines.insert(0, ":".join(_esc(v) for v in (*want, password)))
    _write_pgpass(lines)


def _remove_password(svc: dict) -> None:
    want = list(_key(svc))
    _write_pgpass([l for l in _read_pgpass() if (_split_pgpass(l) or [None])[:4] != want])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_services() -> list[dict]:
    ini = IniFile(service_file())
    out = []
    for name in ini.names():
        vals = ini.get(name) or {}
        pw = lookup_password(vals)
        out.append({
            "name": name,
            **{k: vals.get(k, "") for k in SERVICE_KEYS},
            "extra": {k: v for k, v in vals.items() if k not in SERVICE_KEYS},
            "has_password": pw is not None,
            "password": pw or "",
        })
    return out


def save_service(data: dict, old_name: str | None = None) -> None:
    """
    data: name, host, port, dbname, user, password.
    password=None leaves pgpass untouched; any string (incl. "") sets it.
    """
    name = (data.get("name") or "").strip()
    if not name or any(c in name for c in "[]=\n"):
        raise ValueError(t("err.pg_name"))
    vals = {k: (data.get(k) or "").strip() for k in SERVICE_KEYS}
    if not vals["user"]:
        raise ValueError(t("err.user_required"))
    ini = IniFile(service_file())
    old_vals = ini.get(old_name) if old_name else None
    ini.set(name, vals, old_name=old_name)
    ini.save()

    password = data.get("password")
    if password is None and old_vals and _key(old_vals) != _key(vals):
        # connection target changed — carry the old password over
        password = lookup_password(old_vals)
    if password is not None:
        _set_password(vals, password)


def delete_service(name: str, remove_password: bool = True) -> None:
    ini = IniFile(service_file())
    vals = ini.get(name)
    if vals is None:
        return
    ini.remove(name)
    ini.save()
    if remove_password:
        still_used = any(_key(ini.get(n) or {}) == _key(vals) for n in ini.names())
        if not still_used:
            _remove_password(vals)


def _version_key(path: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", path)]


def find_psql() -> str | None:
    if IS_WINDOWS:
        matches = glob.glob(r"C:\Program Files\PostgreSQL\*\bin\psql.exe")
        if matches:
            return max(matches, key=_version_key)
    return shutil.which("psql")


def test_service(name: str) -> tuple[bool, str]:
    psql = find_psql()
    if not psql:
        return False, t("err.psql_missing")
    env = dict(os.environ, PGCONNECT_TIMEOUT="5")
    try:
        r = subprocess.run(
            [psql, f"service={name}", "-w", "-At", "-c", "select version()"],
            capture_output=True, text=True, timeout=20, env=env,
            stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return False, t("err.timeout")
    out = (r.stdout + r.stderr).strip()
    return r.returncode == 0, out
