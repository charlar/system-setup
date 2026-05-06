# System Setup

One-command machine setup for Windows (CMD) and WSL. Installs **uv**, **git**, and Python, then interactively offers to install:

- MySQL
- PostgreSQL
- Claude Code CLI
- OpenAI Codex CLI
- VS Code

---

## Quick Start

### Windows (CMD)

Open **Command Prompt** and run:

```cmd
curl -fsSL https://raw.githubusercontent.com/charlar/system-setup/main/bootstrap.cmd -o bootstrap.cmd && bootstrap.cmd
```

Or download `bootstrap.cmd` from the repository and double-click it.

### WSL (Ubuntu / Debian)

Open a **WSL terminal** and run:

```bash
curl -fsSL https://raw.githubusercontent.com/charlar/system-setup/main/bootstrap.sh | bash
```

---

## What the bootstrap does

1. Installs **git** (via `winget` on Windows, `apt` on WSL) if not already present.
2. Installs **uv** (the fast Python package manager) if not already present.
3. Clones this repository to `~/system-setup` (or pulls the latest if already cloned).
4. Uses `uv` to install the required Python version.
5. Runs `setup.py` via `uv run`, which checks for each optional tool and asks whether to install it.

---

## Re-running setup

After the initial bootstrap you can re-run setup at any time:

```bash
# WSL
cd ~/system-setup && uv run setup.py
```

```cmd
:: Windows CMD
cd %USERPROFILE%\system-setup && uv run setup.py
```

---

## Prerequisites

| Platform | Requirement |
|----------|-------------|
| Windows  | Windows 10 / 11 with **winget** (App Installer from Microsoft Store) |
| WSL      | Ubuntu 20.04+ or any Debian-based distro |

> **Claude Code** and **Codex** require **Node.js / npm**. If npm is not installed the setup script will prompt you to install it from <https://nodejs.org> before retrying those tools.
