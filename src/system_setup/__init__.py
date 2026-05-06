"""
System setup — checks for required tools and installs on request.
Installed as a uv tool; run with: system-setup
"""
import getpass
import glob
import os
import platform
import subprocess


def _run(cmd: list[str], shell: bool = False) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, check=True, shell=shell)
        return True
    except Exception:
        return False


def _text(cmd: list[str], shell: bool = False) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, shell=shell).stdout.strip()
    except Exception:
        return ""


def _exec(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=False)


IS_WINDOWS = platform.system() == "Windows"
IS_WSL = (
    platform.system() == "Linux"
    and "microsoft" in platform.uname().release.lower()
)

REPO_DIR = os.path.join(os.path.expanduser("~"), "system-setup")

WIN_PROBE_PATTERNS: dict[str, list[str]] = {
    "node": [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
    ],
    "npm": [
        r"C:\Program Files\nodejs\npm.cmd",
        r"C:\Program Files (x86)\nodejs\npm.cmd",
    ],
    "mysql": [
        r"C:\Program Files\MySQL\MySQL Server *\bin\mysql.exe",
        r"C:\Program Files\MySQL\*\bin\mysql.exe",
    ],
    "psql": [
        r"C:\Program Files\PostgreSQL\*\bin\psql.exe",
    ],
    "code": [
        os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd"),
        os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code\code.exe"),
        r"C:\Program Files\Microsoft VS Code\bin\code.cmd",
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files (x86)\Microsoft VS Code\bin\code.cmd",
        r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
    ],
}


def _check(cmd: list[str]) -> bool:
    if _run(cmd):
        return True
    if not IS_WINDOWS:
        return False
    if _run(cmd, shell=True):
        return True
    for pattern in WIN_PROBE_PATTERNS.get(cmd[0], []):
        matches = glob.glob(pattern)
        if matches:
            found = matches[0]
            os.environ["PATH"] = os.path.dirname(found) + ";" + os.environ.get("PATH", "")
            needs_shell = found.lower().endswith((".cmd", ".bat"))
            if _run([found] + cmd[1:], shell=needs_shell):
                return True
    return False


# ---------------------------------------------------------------------------
# Config file paths
# ---------------------------------------------------------------------------

def _pg_dir() -> str:
    if IS_WINDOWS:
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "postgresql")
    return os.path.expanduser("~")


def _pg_service_file() -> str:
    if IS_WINDOWS:
        return os.path.join(_pg_dir(), "pg_service.conf")
    return os.path.expanduser("~/.pg_service.conf")


def _pgpass_file() -> str:
    if IS_WINDOWS:
        return os.path.join(_pg_dir(), "pgpass.conf")
    return os.path.expanduser("~/.pgpass")


def _my_cnf_file() -> str:
    if IS_WINDOWS:
        return os.path.join(os.path.expanduser("~"), "my.cnf")
    return os.path.expanduser("~/.my.cnf")


def _pg_configured() -> bool:
    return os.path.exists(_pg_service_file()) and os.path.exists(_pgpass_file())


def _mysql_configured() -> bool:
    return os.path.exists(_my_cnf_file())


# ---------------------------------------------------------------------------
# Credential prompts + config writers
# ---------------------------------------------------------------------------

def _prompt_password(prompt: str) -> str:
    try:
        return getpass.getpass(f"  {prompt}")
    except Exception:
        return input(f"  {prompt}").strip()


def _configure_postgresql(s: dict) -> None:
    print()
    service = input(f"  {s['pg_service_name']} [local]: ").strip() or "local"
    password = _prompt_password(s["pg_password"])
    if not password:
        return

    os.makedirs(_pg_dir(), exist_ok=True)

    # pg_service.conf — append only if service not already present
    svc_file = _pg_service_file()
    existing = open(svc_file).read() if os.path.exists(svc_file) else ""
    if f"[{service}]" not in existing:
        with open(svc_file, "a") as f:
            f.write(f"\n[{service}]\nhost=localhost\nport=5432\ndbname=postgres\nuser=postgres\n")

    # pgpass — append only if entry not already present
    pass_file = _pgpass_file()
    entry = f"localhost:5432:*:postgres:{password}"
    existing_pass = open(pass_file).read() if os.path.exists(pass_file) else ""
    if "localhost:5432:*:postgres:" not in existing_pass:
        with open(pass_file, "a") as f:
            f.write(entry + "\n")
    if not IS_WINDOWS:
        os.chmod(pass_file, 0o600)

    print(f"  [ok] {s['pg_config_done'].format(service=service)}")


def _configure_mysql(s: dict) -> None:
    print()
    password = _prompt_password(s["mysql_password"])
    if not password:
        return

    cnf = _my_cnf_file()
    existing = open(cnf).read() if os.path.exists(cnf) else ""
    if "[client]" not in existing:
        with open(cnf, "a") as f:
            f.write(f"[client]\nhost=localhost\nuser=root\npassword={password}\n")
        if not IS_WINDOWS:
            os.chmod(cnf, 0o600)
    print(f"  [ok] {s['mysql_config_done']}")


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------

STRINGS = {
    "en": {
        "title":           "=== System Setup ===",
        "lang_prompt":     "Select language / Seleccione idioma:\n  [1] English\n  [2] Español\nChoice / Opción [1]: ",
        "ok":              "already installed",
        "ok_config":       "already installed and configured",
        "ask":             "is not installed. Install it? [y/N] ",
        "ask_config":      "is installed but not configured. Configure it now? [y/N] ",
        "installing":      "Installing",
        "success":         "installed successfully.",
        "reopen":          "installation may need a new terminal session to take effect.",
        "skip":            "Skipping",
        "choco_install":   "Installing Chocolatey (required for Windows installs)...",
        "choco_fail":      "Chocolatey could not be installed. Re-run this script as Administrator.",
        "npm_missing":     "npm is required for {name} but Node.js was not installed or needs a new terminal session.\n      Re-run system-setup to install Node.js first.",
        "npm_note":        "Note: Re-run system-setup and choose to install Node.js, then try again.",
        "update_found":    "A newer version is available. Update now? [y/N] ",
        "updating":        "Updating system-setup...",
        "update_done":     "Updated. Please re-run system-setup.",
        "update_skip":     "Skipping update.",
        "update_err":      "Could not check for updates.",
        "pg_service_name": "PostgreSQL service name for pg_service.conf",
        "pg_password":     "PostgreSQL root (postgres) password: ",
        "pg_config_done":  "pg_service.conf and pgpass written (service='{service}').",
        "mysql_password":  "MySQL root password: ",
        "mysql_config_done": "~/.my.cnf written.",
        "done":            "Setup complete.",
    },
    "es": {
        "title":           "=== Configuración del Sistema ===",
        "lang_prompt":     "Select language / Seleccione idioma:\n  [1] English\n  [2] Español\nChoice / Opción [1]: ",
        "ok":              "ya instalado",
        "ok_config":       "ya instalado y configurado",
        "ask":             "no está instalado. ¿Instalarlo? [s/N] ",
        "ask_config":      "está instalado pero no configurado. ¿Configurarlo ahora? [s/N] ",
        "installing":      "Instalando",
        "success":         "instalado correctamente.",
        "reopen":          "puede requerir una nueva sesión de terminal para tomar efecto.",
        "skip":            "Omitiendo",
        "choco_install":   "Instalando Chocolatey (necesario para instalaciones en Windows)...",
        "choco_fail":      "No se pudo instalar Chocolatey. Vuelva a ejecutar como Administrador.",
        "npm_missing":     "npm es necesario para {name} pero Node.js no fue instalado o requiere una nueva terminal.\n      Vuelva a ejecutar system-setup para instalar Node.js primero.",
        "npm_note":        "Nota: Vuelva a ejecutar system-setup y elija instalar Node.js primero.",
        "update_found":    "Hay una versión más reciente disponible. ¿Actualizar ahora? [s/N] ",
        "updating":        "Actualizando system-setup...",
        "update_done":     "Actualizado. Por favor vuelva a ejecutar system-setup.",
        "update_skip":     "Omitiendo actualización.",
        "update_err":      "No se pudo verificar actualizaciones.",
        "pg_service_name": "Nombre del servicio PostgreSQL para pg_service.conf",
        "pg_password":     "Contraseña de PostgreSQL (usuario postgres): ",
        "pg_config_done":  "pg_service.conf y pgpass escritos (service='{service}').",
        "mysql_password":  "Contraseña de MySQL root: ",
        "mysql_config_done": "~/.my.cnf escrito.",
        "done":            "Configuración completa.",
    },
}

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: dict[str, dict] = {
    "Node.js": {
        "check":       ["node", "--version"],
        "win_install": "choco install nodejs -y --no-progress",
        "wsl_install": "sudo apt-get update -qq && sudo apt-get install -y nodejs npm",
    },
    "npm": {
        "check":       ["npm", "--version"],
        "win_install": "choco install nodejs -y --no-progress",
        "wsl_install": "sudo apt-get update -qq && sudo apt-get install -y nodejs npm",
    },
    "MySQL": {
        "check":        ["mysql", "--version"],
        "config_check": _mysql_configured,
        "configure":    _configure_mysql,
        # password injected at runtime — see _build_install_cmd
        "win_install":  "choco install mysql --params '/RootPassword:{password}' -y --no-progress",
        "wsl_install":  "sudo apt-get update -qq && sudo apt-get install -y mysql-server",
        "wsl_post":     "sudo mysql -e \"ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '{password}'; FLUSH PRIVILEGES;\"",
    },
    "PostgreSQL": {
        "check":        ["psql", "--version"],
        "config_check": _pg_configured,
        "configure":    _configure_postgresql,
        "win_install":  "choco install postgresql --params '/Password:{password}' -y --no-progress",
        "wsl_install":  "sudo apt-get update -qq && sudo apt-get install -y postgresql",
        "wsl_post":     "sudo -u postgres psql -c \"ALTER USER postgres PASSWORD '{password}';\"",
    },
    "Claude Code": {
        "check":       ["claude", "--version"],
        "win_install": "npm install -g @anthropic-ai/claude-code",
        "wsl_install": "npm install -g @anthropic-ai/claude-code",
    },
    "Codex": {
        "check":       ["codex", "--version"],
        "win_install": "npm install -g @openai/codex",
        "wsl_install": "npm install -g @openai/codex",
    },
    "VS Code": {
        "check":       ["code", "--version"],
        "win_install": "choco install vscode -y --no-progress",
        "wsl_install": "sudo snap install code --classic",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _choose_language() -> dict:
    try:
        choice = input(f"\n{STRINGS['en']['lang_prompt']}").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"
    return STRINGS["es"] if choice == "2" else STRINGS["en"]


def _ask(prompt: str, s: dict) -> bool:
    yes_chars = {"y", "s"}
    try:
        return input(f"  {prompt}").strip().lower() in yes_chars
    except (EOFError, KeyboardInterrupt):
        return False


def _npm_available() -> bool:
    return _check(["npm", "--version"])


def _ensure_choco(s: dict) -> bool:
    if _run(["choco", "--version"]) or _run(["choco", "--version"], shell=True):
        return True
    choco_path = os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "chocolatey", "bin")
    if os.path.exists(os.path.join(choco_path, "choco.exe")):
        os.environ["PATH"] = choco_path + ";" + os.environ.get("PATH", "")
        return True
    print(f"  [..] {s['choco_install']}")
    _exec(
        'powershell -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command '
        '"[System.Net.ServicePointManager]::SecurityProtocol = 3072; '
        "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))\""
    )
    os.environ["PATH"] = choco_path + ";" + os.environ.get("PATH", "")
    if _run(["choco", "--version"]) or _run(["choco", "--version"], shell=True):
        return True
    print(f"  [!] {s['choco_fail']}")
    return False


def _check_for_updates(s: dict) -> bool:
    if not os.path.exists(os.path.join(REPO_DIR, ".git")):
        return False
    try:
        subprocess.run(
            ["git", "-C", REPO_DIR, "fetch", "--quiet"],
            capture_output=True, timeout=10,
        )
        local  = _text(["git", "-C", REPO_DIR, "rev-parse", "HEAD"])
        remote = _text(["git", "-C", REPO_DIR, "rev-parse", "@{u}"])
        if not local or not remote or local == remote:
            return False
    except Exception:
        print(f"  [!] {s['update_err']}")
        return False

    if not _ask(s["update_found"], s):
        print(f"  {s['update_skip']}")
        return False

    print(f"  {s['updating']}")
    subprocess.run(["git", "-C", REPO_DIR, "pull", "--ff-only"], check=False)
    subprocess.run(["uv", "tool", "install", REPO_DIR, "--reinstall"], check=False)
    print(f"\n  {s['update_done']}")
    return True


def _prompt_install_password(name: str, cfg: dict, s: dict) -> str:
    """Ask for a password when it's needed for both install and config."""
    if "configure" not in cfg:
        return ""
    key = "pg_password" if name == "PostgreSQL" else "mysql_password"
    return _prompt_password(s[key])


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    s = _choose_language()
    print(f"\n{s['title']}\n")

    if _check_for_updates(s):
        return

    choco_ready = not IS_WINDOWS
    npm_needed  = False

    for name, cfg in TOOLS.items():
        installed = _check(cfg["check"])
        has_config = "configure" in cfg
        configured = has_config and cfg["config_check"]()

        if installed and (not has_config or configured):
            print(f"  [ok] {name} — {s['ok_config' if configured else 'ok']}")
            continue

        if installed and has_config and not configured:
            # Tool present but config files missing — offer to configure only
            if _ask(f"{name} {s['ask_config']}", s):
                cfg["configure"](s)
            else:
                print(f"  [--] {s['skip']} {name}")
            continue

        # Not installed
        if not _ask(f"{name} {s['ask']}", s):
            print(f"  [--] {s['skip']} {name}")
            continue

        # Prompt for password before install (needed in install cmd and config)
        password = ""
        if has_config:
            password = _prompt_install_password(name, cfg, s)

        install_cmd = cfg["win_install"] if IS_WINDOWS else cfg["wsl_install"]
        install_cmd = install_cmd.format(password=password)

        if IS_WINDOWS and "choco" in install_cmd:
            if not choco_ready:
                choco_ready = _ensure_choco(s)
            if not choco_ready:
                continue

        if "npm install" in install_cmd and not _npm_available():
            npm_needed = True
            print(f"  [!] {s['npm_missing'].format(name=name)}")
            continue

        print(f"  {s['installing']} {name}...")
        _exec(install_cmd)

        # WSL post-install password setup
        if not IS_WINDOWS and password and "wsl_post" in cfg:
            _exec(cfg["wsl_post"].format(password=password))

        if _check(cfg["check"]):
            print(f"  [ok] {name} {s['success']}")
            if has_config and password:
                cfg["configure"](s)
        else:
            print(f"  [!] {name} {s['reopen']}")

    if npm_needed:
        print(f"\n  {s['npm_note']}")

    print(f"\n{s['done']}\n")
