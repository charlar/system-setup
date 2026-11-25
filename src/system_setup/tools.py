"""
Windows tool catalog for the GUI: detection, install and removal steps.
To add a tool, add an entry to CATALOG — most only need `choco` and `check`.
"""
import glob
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field

from . import myconfig, pgconfig
from .jobs import Job, Step, run_cmd
from .i18n import t
from .winenv import IS_WINDOWS, NO_WINDOW, refresh_path

HOME = os.path.expanduser("~")


@dataclass
class Tool:
    id: str
    name: str
    description: str
    check: list[str]                         # command that prints a version
    choco: str | None = None                 # choco package to install
    choco_match: str | None = None           # regex of choco package names that count as installed
    probe: list[str] = field(default_factory=list)   # extra places to look for check[0]
    needs_password: bool = False
    needs_npm: bool = False
    note: str = ""

    @property
    def needs_admin(self) -> bool:
        return self.choco is not None


CATALOG: list[Tool] = [
    Tool("git", "Git", "Version control.", ["git", "--version"], choco="git", choco_match=r"git(\.install)?"),
    Tool("node", "Node.js (LTS)", "JavaScript runtime and npm. Needed for Codex.",
         ["node", "--version"], choco="nodejs-lts", choco_match=r"nodejs(-lts)?(\.install)?",
         probe=[r"C:\Program Files\nodejs\node.exe"]),
    Tool("postgresql", "PostgreSQL", "Database server + psql. Sets the 'postgres' user password.",
         ["psql", "--version"], choco="postgresql", choco_match=r"postgresql\d*",
         probe=[r"C:\Program Files\PostgreSQL\*\bin\psql.exe"], needs_password=True,
         note="Also creates a psql service named 'root' (psql service=root)."),
    Tool("mysql", "MySQL", "Database server + mysql client. Sets the root password.",
         ["mysql", "--version"], choco="mysql", choco_match=r"mysql",
         probe=[r"C:\tools\mysql\*\bin\mysql.exe", r"C:\Program Files\MySQL\*\bin\mysql.exe"],
         needs_password=True,
         note="Also creates a login named 'root' (mysql --defaults-group-suffix=root)."),
    Tool("vscode", "VS Code", "Code editor.", ["code", "--version"], choco="vscode", choco_match=r"vscode(\.install)?",
         probe=[os.path.join(HOME, r"AppData\Local\Programs\Microsoft VS Code\bin\code.cmd"),
                r"C:\Program Files\Microsoft VS Code\bin\code.cmd"]),
    Tool("gh", "GitHub CLI", "GitHub from the command line (gh).", ["gh", "--version"], choco="gh", choco_match=r"gh"),
    Tool("claude", "Claude Code", "Anthropic's coding agent CLI (native installer, auto-updates).",
         ["claude", "--version"], probe=[os.path.join(HOME, r".local\bin\claude.exe")]),
    Tool("codex", "Codex", "OpenAI's coding agent CLI (installed with npm).",
         ["codex", "--version"], needs_npm=True,
         probe=[os.path.join(os.environ.get("APPDATA", ""), r"npm\codex.cmd")]),
]

BY_ID = {t.id: t for t in CATALOG}


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _quiet(argv: list[str], timeout: int = 20) -> subprocess.CompletedProcess | None:
    try:
        shell = argv[0].lower().endswith((".cmd", ".bat"))
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, shell=shell,
            stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def choco_exe() -> str | None:
    found = shutil.which("choco")
    if found:
        return found
    p = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "chocolatey", "bin", "choco.exe")
    return p if os.path.exists(p) else None


def choco_packages() -> dict[str, str]:
    """Locally installed choco packages -> version (choco v2: `list` is local-only)."""
    choco = choco_exe()
    if not choco:
        return {}
    r = _quiet([choco, "list", "--limit-output"], timeout=60)
    out: dict[str, str] = {}
    for line in (r.stdout if r else "").splitlines():
        if "|" in line:
            name, ver = line.split("|", 1)
            out[name.strip().lower()] = ver.strip()
    return out


def find_exe(tool: Tool) -> str | None:
    # psql/mysql: on PATH we'd find our own wrapper commands, so look for the real install
    if tool.id == "postgresql":
        return pgconfig.find_psql() if IS_WINDOWS else shutil.which("psql")
    if tool.id == "mysql":
        return myconfig.find_mysql() if IS_WINDOWS else shutil.which("mysql")
    found = shutil.which(tool.check[0])
    if found:
        return found
    matches = [m for p in tool.probe for m in glob.glob(p)]
    return max(matches, key=pgconfig._version_key) if matches else None


def _is_npm_install(path: str) -> bool:
    return os.path.normcase(os.path.join(os.environ.get("APPDATA", ""), "npm")) in os.path.normcase(path)


def status(tool: Tool, pkgs: dict[str, str]) -> dict:
    choco_pkg = next((p for p in pkgs if tool.choco_match and re.fullmatch(tool.choco_match, p)), None)
    exe = find_exe(tool)
    version = ""
    if exe:
        r = _quiet([exe] + tool.check[1:])
        text = ((r.stdout or r.stderr) if r and r.returncode == 0 else "").strip()
        version = text.splitlines()[0] if text else ""
        if " Ver " in version:          # mysql prints its full path first
            version = "mysql Ver " + version.split(" Ver ", 1)[1]
    if not version and choco_pkg:
        version = pkgs[choco_pkg]
    installed = bool(exe or choco_pkg)
    return {
        "id": tool.id,
        "name": tool.name,
        "description": t(f"tool.{tool.id}.desc"),
        "note": t(f"tool.{tool.id}.note") if tool.note else "",
        "installed": installed,
        "version": version,
        "path": exe or "",
        "source": "choco" if choco_pkg else ("other" if installed else ""),
        "needs_password": tool.needs_password,
        "needs_admin": tool.needs_admin,
        # we only remove what we know how to remove cleanly
        "can_remove": bool(choco_pkg) or tool.id in ("claude", "codex"),
    }


def all_status() -> list[dict]:
    refresh_path()
    pkgs = choco_packages()
    return [status(t, pkgs) for t in CATALOG]


# ---------------------------------------------------------------------------
# Install / remove steps
# ---------------------------------------------------------------------------

def _sql_str(v: str) -> str:
    return v.replace("\\", "\\\\").replace("'", "''")


def _check_choco_password(pw: str) -> None:
    # choco splits package params on '/' and spaces; quotes break its parser
    if not pw:
        raise ValueError(t("err.password_required"))
    bad = set(pw) & set("/ '\"")
    if bad:
        raise ValueError(t("err.choco_password"))


def _ps(script: str, display: str) -> Step:
    return Step(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], display=display)


def _ensure_choco(job: Job) -> bool:
    if choco_exe():
        return True
    job.log(t("log.choco_installing"))
    ok = run_cmd(job, Step(
        ["powershell", "-NoProfile", "-InputFormat", "None", "-ExecutionPolicy", "Bypass", "-Command",
         "[System.Net.ServicePointManager]::SecurityProtocol = 3072; "
         "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"],
        display="Install Chocolatey (community.chocolatey.org/install.ps1)", elevated=True))
    refresh_path()
    if ok and choco_exe():
        return True
    job.log(t("log.choco_failed"))
    return False


def _choco(*args: str, display: str = "") -> Step:
    """A choco step that resolves choco.exe at run time (it may have just been installed)."""
    def run(job: Job) -> bool:
        return run_cmd(job, Step([choco_exe() or "choco", *args], display=display or "choco " + " ".join(args),
                                 elevated=True))
    return Step(call=run)


def generate_password(length: int = 20) -> str:
    # letters + digits only: safe for choco's parameter parser, option files and SQL
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def install_steps(tool: Tool, password: str = "") -> list[Step]:
    generated = False
    if tool.needs_password and not password:
        # Install with a strong random password; it's saved to the 'root' service/login,
        # where it can be revealed or replaced later with "Change password".
        password, generated = generate_password(), True
    if tool.id == "claude":
        return [_ps("irm https://claude.ai/install.ps1 | iex", "irm https://claude.ai/install.ps1 | iex")]
    if tool.id == "codex":
        return [Step(call=_require_npm), Step(call=lambda job: _npm(job, "install", "@openai/codex"))]

    if tool.id == "postgresql":
        _check_choco_password(password)
        return [
            Step(call=_ensure_choco),
            _choco("install", "postgresql", "-y", "--no-progress",
                   "--params", f"/Password:{password}", "--params-global",
                   display="choco install postgresql -y --no-progress --params /Password:******** --params-global"),
            Step(call=lambda job: _pg_post(job, password, generated)),
        ]
    if tool.id == "mysql":
        myconfig._quote(password)   # validates
        return [
            Step(call=_ensure_choco),
            _choco("install", "mysql", "-y", "--no-progress"),
            Step(call=lambda job: _mysql_post(job, password, generated)),
        ]
    return [Step(call=_ensure_choco), _choco("install", tool.choco, "-y", "--no-progress")]


def remove_steps(tool: Tool) -> list[Step]:
    if tool.id == "claude" and _is_npm_install(find_exe(tool) or ""):
        return [Step(call=_require_npm), Step(call=lambda job: _npm(job, "uninstall", "@anthropic-ai/claude-code"))]
    if tool.id == "claude":
        return [_ps(
            "Remove-Item -Path \"$env:USERPROFILE\\.local\\bin\\claude.exe\" -Force -ErrorAction SilentlyContinue; "
            "Remove-Item -Path \"$env:USERPROFILE\\.local\\share\\claude\" -Recurse -Force -ErrorAction SilentlyContinue",
            t("log.claude_remove"))]
    if tool.id == "codex":
        return [Step(call=_require_npm), Step(call=lambda job: _npm(job, "uninstall", "@openai/codex"))]
    pkgs = [p for p in choco_packages() if tool.choco_match and re.fullmatch(tool.choco_match, p)]
    if not pkgs:
        raise ValueError(t("err.not_choco", name=tool.name))
    # remove the meta package (e.g. 'postgresql') before its versioned dependency
    pkgs.sort(key=lambda p: (p != tool.choco, p))
    return [_choco("uninstall", *pkgs, "-y", "--no-progress")]


# ---- helper steps -----------------------------------------------------------

def _npm_exe() -> str | None:
    refresh_path()
    return shutil.which("npm") or next(iter(glob.glob(r"C:\Program Files\nodejs\npm.cmd")), None)


def _require_npm(job: Job) -> bool:
    if _npm_exe():
        return True
    job.log(t("log.npm_missing"))
    return False


def _npm(job: Job, action: str, pkg: str) -> bool:
    step = Step([_npm_exe(), action, "-g", pkg], display=f"npm {action} -g {pkg}")
    # npm is a .cmd file; run it through cmd so CreateProcess can start it
    step.argv = ["cmd", "/c", *step.argv]
    return run_cmd(job, step)


def _pg_password_works(password: str) -> bool:
    psql = pgconfig.find_psql()
    r = _quiet_env([psql, "-h", "localhost", "-p", "5432", "-U", "postgres", "-d", "postgres",
                    "-w", "-X", "-At", "-c", "select 1"], {"PGPASSWORD": password, "PGCONNECT_TIMEOUT": "10"})
    return bool(r and r.returncode == 0)


def _quiet_env(argv: list[str], extra_env: dict[str, str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
                              env=dict(os.environ, **extra_env), creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _pg_post(job: Job, password: str, generated: bool) -> bool:
    refresh_path()
    if not pgconfig.find_psql():
        job.log(t("log.psql_missing"))
        return True
    svc = {"name": "root", "host": "localhost", "port": "5432", "dbname": "postgres", "user": "postgres",
           "password": password}
    existing = {s["name"] for s in pgconfig.list_services()}
    if _pg_password_works(password):
        pgconfig.save_service(svc, old_name="root" if "root" in existing else None)
        job.log(t("log.pg_root_saved", path=pgconfig.service_file()))
        if generated:
            job.log(t("log.pw_generated_pg"))
    elif "root" not in existing:
        # can't verify (server still starting?) — save it anyway so it isn't lost
        pgconfig.save_service(svc)
        job.log(t("log.pg_unverified", name="root"))
    else:
        # Don't overwrite a working 'root' with a password we couldn't verify. (pgpass keys
        # passwords by server+user, so a second service for 'postgres' can't hold a different
        # one.) Usually this means PostgreSQL was already installed and kept its old password.
        job.log(t("log.pg_kept_root", password=password if generated else "********"))
    return True


def _mysql_post(job: Job, password: str, generated: bool) -> bool:
    refresh_path()
    mysql = myconfig.find_mysql()
    if not mysql:
        job.log(t("log.mysql_missing"))
        return False
    job.log("> mysql -u root --skip-password  (ALTER USER 'root'@'localhost' IDENTIFIED BY '********')")
    # a fresh choco install leaves root with no password; the SQL goes over stdin
    r = subprocess.run(
        [mysql, "--no-defaults", "-u", "root", "--skip-password", "--connect-timeout=10"],
        input=f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{_sql_str(password)}';\n",
        capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW,
    )
    if r.returncode != 0:
        job.log((r.stdout + r.stderr).strip())
        job.log(t("log.mysql_pw_failed"))
        return True        # install itself worked; the login just isn't saved
    existing = {l["name"] for l in myconfig.list_logins()}
    myconfig.save_login({"name": "root", "host": "localhost", "user": "root", "password": password},
                        old_name="root" if "root" in existing else None)
    job.log(t("log.my_root_saved", path=myconfig.option_file()))
    if generated:
        job.log(t("log.pw_generated_my"))
    return True
