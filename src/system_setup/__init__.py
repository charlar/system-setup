"""
System setup — checks for required tools and installs on request.
Installed as a uv tool; run with: system-setup
"""
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


def _exec(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=False)


IS_WINDOWS = platform.system() == "Windows"
IS_WSL = (
    platform.system() == "Linux"
    and "microsoft" in platform.uname().release.lower()
)

# Glob patterns for common Windows install locations not always on PATH.
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
    """Check if a command runs, probing known Windows install paths as fallback."""
    if _run(cmd):
        return True
    if not IS_WINDOWS:
        return False
    # On Windows, .cmd/.bat files on PATH need shell=True to be found by name
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


STRINGS = {
    "en": {
        "title":         "=== System Setup ===",
        "lang_prompt":   "Select language / Seleccione idioma:\n  [1] English\n  [2] Español\nChoice / Opción [1]: ",
        "ok":            "already installed",
        "ask":           "is not installed. Install it? [y/N] ",
        "installing":    "Installing",
        "success":       "installed successfully.",
        "reopen":        "installation may need a new terminal session to take effect.",
        "skip":          "Skipping",
        "choco_install": "Installing Chocolatey (required for Windows installs)...",
        "choco_fail":    "Chocolatey could not be installed. Re-run this script as Administrator.",
        "npm_missing":   "npm is required for {name} but Node.js was not installed or needs a new terminal session.\n      Re-run system-setup to install Node.js first.",
        "npm_note":      "Note: Re-run system-setup and choose to install Node.js, then try again.",
        "done":          "Setup complete.",
    },
    "es": {
        "title":         "=== Configuración del Sistema ===",
        "lang_prompt":   "Select language / Seleccione idioma:\n  [1] English\n  [2] Español\nChoice / Opción [1]: ",
        "ok":            "ya instalado",
        "ask":           "no está instalado. ¿Instalarlo? [s/N] ",
        "installing":    "Instalando",
        "success":       "instalado correctamente.",
        "reopen":        "puede requerir una nueva sesión de terminal para tomar efecto.",
        "skip":          "Omitiendo",
        "choco_install": "Instalando Chocolatey (necesario para instalaciones en Windows)...",
        "choco_fail":    "No se pudo instalar Chocolatey. Vuelva a ejecutar como Administrador.",
        "npm_missing":   "npm es necesario para {name} pero Node.js no fue instalado o requiere una nueva terminal.\n      Vuelva a ejecutar system-setup para instalar Node.js primero.",
        "npm_note":      "Nota: Vuelva a ejecutar system-setup y elija instalar Node.js primero.",
        "done":          "Configuración completa.",
    },
}

TOOLS = {
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
        "check":       ["mysql", "--version"],
        "win_install": "choco install mysql -y --no-progress",
        "wsl_install": "sudo apt-get update -qq && sudo apt-get install -y mysql-server",
    },
    "PostgreSQL": {
        "check":       ["psql", "--version"],
        "win_install": "choco install postgresql -y --no-progress",
        "wsl_install": "sudo apt-get update -qq && sudo apt-get install -y postgresql",
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


def _choose_language() -> dict:
    try:
        choice = input(f"\n{STRINGS['en']['lang_prompt']}").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"
    return STRINGS["es"] if choice == "2" else STRINGS["en"]


def _ask(name: str, s: dict) -> bool:
    yes_chars = {"y", "s"}
    try:
        return input(f"  {name} {s['ask']}").strip().lower() in yes_chars
    except (EOFError, KeyboardInterrupt):
        return False


def _npm_available() -> bool:
    return _check(["npm", "--version"])


def _ensure_choco(s: dict) -> bool:
    if _run(["choco", "--version"]):
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
    if _run(["choco", "--version"]):
        return True
    print(f"  [!] {s['choco_fail']}")
    return False


def main() -> None:
    s = _choose_language()
    print(f"\n{s['title']}\n")

    choco_ready = not IS_WINDOWS
    npm_needed = False

    for name, cfg in TOOLS.items():
        if _check(cfg["check"]):
            print(f"  [ok] {name} — {s['ok']}")
            continue

        if not _ask(name, s):
            print(f"  [--] {s['skip']} {name}")
            continue

        install_cmd = cfg["win_install"] if IS_WINDOWS else cfg["wsl_install"]

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

        if _check(cfg["check"]):
            print(f"  [ok] {name} {s['success']}")
        else:
            print(f"  [!] {name} {s['reopen']}")

    if npm_needed:
        print(f"\n  {s['npm_note']}")

    print(f"\n{s['done']}\n")
