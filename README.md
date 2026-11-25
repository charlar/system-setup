# System Setup

> Para instrucciones en español, ver [README.es.md](README.es.md)

One-command machine setup for Windows (CMD) and WSL. Installs **uv**, **git**, and Python, registers the `system-setup`, `psql`, and `mysql` commands, then interactively offers to install:

- Node.js / npm
- MySQL
- PostgreSQL
- Claude Code CLI
- OpenAI Codex CLI
- VS Code

---

## Quick Start

### Windows (CMD) — run as Administrator

Open **Command Prompt as Administrator** and run:

```cmd
curl -fsSL https://raw.githubusercontent.com/charlar/system-setup/master/bootstrap.cmd -o bootstrap.cmd && bootstrap.cmd
```

Or download `bootstrap.cmd` from the repository and right-click → **Run as administrator**.

### WSL (Ubuntu / Debian)

Open a **WSL terminal** and run:

```bash
curl -fsSL https://raw.githubusercontent.com/charlar/system-setup/master/bootstrap.sh | bash
```

---

## What the bootstrap does

1. Installs **Chocolatey** (Windows) or uses **apt** (WSL) as the package manager.
2. Installs **git** if not already present.
3. Installs **uv** (fast Python package manager) if not already present.
4. Clones this repository to `~/system-setup` (or pulls the latest if already cloned).
5. Uses `uv` to install the required Python version.
6. Runs `uv tool install . --reinstall` to register the `system-setup`, `system-setupg`, `psql`, and `mysql` commands.
7. Asks whether to continue in the **desktop app** (`system-setupg`, the default after 30 seconds) or the **command line** (`system-setup`). On WSL it runs the command line.
8. Adds **System Setup** to the Start menu (Windows).

---

## Re-running setup

After the initial bootstrap, open **Start menu → System Setup**, or run from any terminal:

```cmd
system-setupg   :: desktop app (Windows)
system-setup    :: command line
```

---

## system-setupg (desktop app, Windows)

After setup, run `system-setupg` (Start → Run, or any terminal) for a window where you can:

- **Windows tools** — see what's installed and install/remove Git, Node.js, PostgreSQL, MySQL, VS Code, GitHub CLI, Claude Code and Codex.
- **WSL & Docker** — install Docker Engine inside your WSL distro (enables systemd, adds you to the `docker` group), or install/remove apt packages. Runs as root via `wsl -u root`, so there's no sudo prompt.
- **PostgreSQL** — add/edit/delete/test saved connections (`psql service=name`), with passwords kept in pgpass.
- **MySQL** — the same for saved logins (`mysql --defaults-group-suffix=name`).
- **Config files** — every config file's location, with Edit and Show in folder buttons.

Chocolatey needs administrator rights:

- **Admin account:** it asks once when it starts. If you say no, each Chocolatey install asks instead.
- **Standard account:** the window runs as you (so saved connections stay in your own profile), and each Chocolatey install asks for an administrator's password.

When a new version is pushed, a banner offers **Update and restart**.

The language (English/Español) switch is at the bottom left. The choice is remembered in `%APPDATA%\system-setup\settings.ini` and shared with `system-setup`, which now asks only once (`system-setup --language` to change it).

Logs: `%LOCALAPPDATA%\system-setup\gui.log`. Use `system-setupg --debug` to get browser dev tools.

---

## psql and mysql wrappers

The `psql` and `mysql` commands are installed as wrappers that find the real binary even when it is not on PATH (common on Windows after a GUI install). All command-line arguments are passed through unchanged:

```cmd
psql service="root"
mysql --defaults-group-suffix=root
```

---

## Prerequisites

| Platform | Requirement |
|----------|-------------|
| Windows  | Windows 10 / 11, **Administrator** privileges |
| WSL      | Ubuntu 20.04+ or any Debian-based distro |
