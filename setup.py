"""
System setup script — checks for required tools and installs on request.
Run via: uv run setup.py
"""
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

STRINGS = {
    "en": {
        "title":        "=== System Setup ===",
        "lang_prompt":  "Select language / Seleccione idioma:\n  [1] English\n  [2] Español\nChoice / Opción [1]: ",
        "ok":           "already installed",
        "ask":          "is not installed. Install it? [y/N] ",
        "installing":   "Installing",
        "success":      "installed successfully.",
        "reopen":       "installation may need a new terminal session to take effect.",
        "skip":         "Skipping",
        "npm_missing":  "npm is required for {name} but is not installed.\n      Install Node.js from https://nodejs.org then re-run this script.",
        "npm_note":     "Note: Install Node.js (https://nodejs.org) then re-run to install npm-based tools.",
        "done":         "Setup complete.",
    },
    "es": {
        "title":        "=== Configuración del Sistema ===",
        "lang_prompt":  "Select language / Seleccione idioma:\n  [1] English\n  [2] Español\nChoice / Opción [1]: ",
        "ok":           "ya instalado",
        "ask":          "no está instalado. ¿Instalarlo? [s/N] ",
        "installing":   "Instalando",
        "success":      "instalado correctamente.",
        "reopen":       "puede requerir una nueva sesión de terminal para tomar efecto.",
        "skip":         "Omitiendo",
        "npm_missing":  "npm es necesario para {name} pero no está instalado.\n      Instale Node.js desde https://nodejs.org y vuelva a ejecutar.",
        "npm_note":     "Nota: Instale Node.js (https://nodejs.org) y vuelva a ejecutar para instalar herramientas npm.",
        "done":         "Configuración completa.",
    },
}

TOOLS = {
    "MySQL": {
        "check":       ["mysql", "--version"],
        "win_install": "winget install --id Oracle.MySQL -e --accept-package-agreements --accept-source-agreements",
        "wsl_install": "sudo apt-get update -qq && sudo apt-get install -y mysql-server",
    },
    "PostgreSQL": {
        "check":       ["psql", "--version"],
        "win_install": "winget install --id PostgreSQL.PostgreSQL -e --accept-package-agreements --accept-source-agreements",
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
        "win_install": "winget install --id Microsoft.VisualStudioCode -e --accept-package-agreements --accept-source-agreements",
        "wsl_install": "sudo snap install code --classic",
    },
}


def _choose_language() -> dict:
    prompt = STRINGS["en"]["lang_prompt"]
    try:
        choice = input(f"\n{prompt}").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"
    return STRINGS["es"] if choice == "2" else STRINGS["en"]


def _ask(name: str, s: dict) -> bool:
    yes_chars = {"y", "s"}  # English y / Spanish s
    try:
        answer = input(f"  {name} {s['ask']}").strip().lower()
        return answer in yes_chars
    except (EOFError, KeyboardInterrupt):
        return False


def _npm_available() -> bool:
    return _run(["npm", "--version"])


def main() -> None:
    s = _choose_language()
    print(f"\n{s['title']}\n")

    npm_needed = False

    for name, cfg in TOOLS.items():
        if _run(cfg["check"]):
            print(f"  [ok] {name} — {s['ok']}")
        else:
            if _ask(name, s):
                install_cmd = cfg["win_install"] if IS_WINDOWS else cfg["wsl_install"]
                if "npm install" in install_cmd and not _npm_available():
                    npm_needed = True
                    print(f"  [!] {s['npm_missing'].format(name=name)}")
                    continue
                print(f"  {s['installing']} {name}...")
                _exec(install_cmd)
                if _run(cfg["check"]):
                    print(f"  [ok] {name} {s['success']}")
                else:
                    print(f"  [!] {name} {s['reopen']}")
            else:
                print(f"  [--] {s['skip']} {name}")

    if npm_needed:
        print(f"\n  {s['npm_note']}")

    print(f"\n{s['done']}\n")


if __name__ == "__main__":
    main()
