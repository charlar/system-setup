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
6. Runs `uv tool install . --reinstall` to register `system-setup`, `psql`, and `mysql` commands.
7. Runs `system-setup`, which checks for each optional tool and asks whether to install it.

---

## Re-running setup

After the initial bootstrap, run from any terminal:

```cmd
system-setup
```

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
