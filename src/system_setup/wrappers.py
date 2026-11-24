"""
Thin wrappers for psql and mysql that find the real binary even when it's
not on PATH (common on Windows), then exec it with all args passed through.
Installed as uv tool entry points: psql / mysql

On Windows the mysql wrapper also adds --defaults-extra-file=~/my.cnf, because
the Windows mysql client never reads a per-user option file on its own — that's
what makes `mysql --defaults-group-suffix=root` pick up saved logins.
"""
import glob
import os
import platform
import subprocess
import sys

from .myconfig import option_file

IS_WINDOWS = platform.system() == "Windows"


def _newest(patterns: list[str]) -> str | None:
    from .pgconfig import _version_key
    matches = [m for p in patterns for m in glob.glob(p)]
    return max(matches, key=_version_key) if matches else None


PSQL_PATTERNS = [r"C:\Program Files\PostgreSQL\*\bin\psql.exe"]
MYSQL_PATTERNS = [
    r"C:\Program Files\MySQL\*\bin\mysql.exe",
    r"C:\tools\mysql\*\bin\mysql.exe",          # choco 'mysql' package
]


def _find_real(name: str, win_patterns: list[str]) -> str | None:
    """Find the real executable without risking calling our own wrapper."""
    if IS_WINDOWS:
        # Skip PATH entirely on Windows — the wrapper exists because the real
        # binary is NOT on PATH. Go straight to known install locations.
        return _newest(win_patterns)

    # Linux/WSL: search PATH but skip our own exe using samefile() for reliability
    our = os.path.abspath(sys.argv[0])
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            try:
                if not os.path.samefile(candidate, our):
                    return candidate
            except OSError:
                if os.path.abspath(candidate) != our:
                    return candidate
    return None


def _exec(name: str, patterns: list[str], prefix: list[str] | None = None) -> None:
    exe = _find_real(name, patterns)
    if not exe:
        print(f"{name} not found. Install it with system-setupg or system-setup.", file=sys.stderr)
        sys.exit(1)
    args = (prefix or []) + sys.argv[1:]
    if IS_WINDOWS:
        # os.execv on Windows doesn't replace the process, so use subprocess instead.
        # stdio is inherited so interactive sessions work fine.
        result = subprocess.run([exe] + args)
        sys.exit(result.returncode)
    else:
        # Replace the wrapper process entirely — psql/mysql owns the terminal directly.
        os.execv(exe, [exe] + args)


def psql() -> None:
    _exec("psql", PSQL_PATTERNS)


def mysql() -> None:
    prefix: list[str] = []
    user_args = sys.argv[1:]
    overrides = ("--no-defaults", "--defaults-file", "--defaults-extra-file", "--print-defaults")
    if IS_WINDOWS and os.path.exists(option_file()) and not any(a.startswith(overrides) for a in user_args[:1]):
        # Option-file flags must be the very first argument
        prefix = [f"--defaults-extra-file={option_file()}"]
    _exec("mysql", MYSQL_PATTERNS, prefix)
