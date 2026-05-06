"""
System setup script — checks for required tools and installs on request.
Run via: uv run setup.py
"""
import glob
import os
import platform
import subprocess


def _run(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _exec(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=False)


IS_WINDOWS = platform.system() == "Windows"
IS_WSL = (
    platform.system() == "Linux"
    and "microsoft" in platform.uname().release.lower()
)

# Glob patterns for common Windows install locations not always on PATH.
# If a match is found its parent directory is added to PATH for this session.
WIN_PROBE_PATTERNS: dict[str, list[str]] = {
    "mysql": [
        r"C:\Program Files\MySQL\MySQL Server *\bin\mysql.exe",
        r"C:\Program Files\MySQL\*\bin\mysql.exe",
    ],
    "psql": [
        r"C:\Program Files\PostgreSQL\*\bin\psql.exe",
    ],
    "code": [
        os.path.expanduser(r"~\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd"),
        r"C:\Program Files\Microsoft VS Code\bin\code.cmd",
        r"C:\Program Files (x86)\Microsoft VS Code\bin\code.cmd",
    ],
}


def _probe_win_path(exe: str) -> bool:
    """Check known install locations on Windows and add the directory to PATH if found."""
    for pattern in WIN_PROBE_PATTERNS.get(exe, []):
        matches = glob.glob(pattern)
        if matches:
            bin_dir = os.path.dirname(matches[0])
            os.environ["PATH"] = bin_dir + ";" + os.environ.get("PATH", "")
            return True
    return False


def _check(cmd: list[str]) -> bool:
    """Check if a command is available, probing known paths on Windows if needed."""
    if _run(cmd):
        return True
    if IS_WINDOWS and _probe_win_path(cmd[0]):
        return _run(cmd)
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
        "npm_missing":   "npm is required for {name} but is not installed.\n      Install Node.js then re-run: choco install nodejs -y",
        "npm_note":      "Note: Run 'choco install nodejs -y' in an admin CMD, then re-run this script.",
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
        "npm_missing":   "npm es necesario para {name} pero no está instalado.\n      Instale Node.js y vuelva a ejecutar: choco install nodejs -y",
        "npm_note":      "Nota: Ejecute 'choco install nodejs -y' en un CMD como admin y vuelva a ejecutar.",
        "done":          "Configuración completa.",
    },
}

TOOLS = {
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
    return _run(["npm", "--version"])


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


if __name__ == "__main__":
    main()
