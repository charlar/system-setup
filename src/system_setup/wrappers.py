"""
Thin wrappers for psql and mysql that find the real binary even when it's
not on PATH (common on Windows), then exec it with all args passed through.
Installed as uv tool entry points: psql / mysql
"""
import glob
import os
import platform
import subprocess
import sys

IS_WINDOWS = platform.system() == "Windows"

PSQL_PATTERNS = [
    r"C:\Program Files\PostgreSQL\*\bin\psql.exe",
]

MYSQL_PATTERNS = [
    r"C:\Program Files\MySQL\MySQL Server *\bin\mysql.exe",
    r"C:\Program Files\MySQL\*\bin\mysql.exe",
]


def _find_real(name: str, win_patterns: list[str]) -> str | None:
    """Find the real executable, skipping our own wrapper to avoid recursion."""
    our = os.path.normcase(os.path.abspath(sys.argv[0]))
    exts = ["", ".exe", ".cmd"] if IS_WINDOWS else [""]

    for directory in os.environ.get("PATH", "").split(os.pathsep):
        for ext in exts:
            candidate = os.path.join(directory, name + ext)
            if os.path.isfile(candidate) and os.path.normcase(os.path.abspath(candidate)) != our:
                return candidate

    if IS_WINDOWS:
        for pattern in win_patterns:
            matches = glob.glob(pattern)
            if matches:
                return matches[0]

    return None


def _exec(name: str, patterns: list[str]) -> None:
    exe = _find_real(name, patterns)
    if not exe:
        print(f"{name} not found. Install it and re-run system-setup.", file=sys.stderr)
        sys.exit(1)
    if IS_WINDOWS:
        # os.execv on Windows doesn't replace the process, so use subprocess instead.
        # stdio is inherited so interactive sessions work fine.
        result = subprocess.run([exe] + sys.argv[1:])
        sys.exit(result.returncode)
    else:
        # Replace the wrapper process entirely — psql/mysql owns the terminal directly.
        os.execv(exe, [exe] + sys.argv[1:])


def psql() -> None:
    _exec("psql", PSQL_PATTERNS)


def mysql() -> None:
    _exec("mysql", MYSQL_PATTERNS)
