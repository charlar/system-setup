# System Setup

One-command machine setup for Windows (CMD) and WSL. Installs **uv**, **git**, and Python, registers the `system-setup` command, then interactively offers to install:

- Node.js
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
6. Runs `uv tool install .` to register the `system-setup` command.
7. Runs `system-setup`, which checks for each optional tool and asks whether to install it.

---

## Re-running setup

After the initial bootstrap, run from any terminal:

```cmd
system-setup
```

---

## Prerequisites

| Platform | Requirement |
|----------|-------------|
| Windows  | Windows 10 / 11, **Administrator** privileges |
| WSL      | Ubuntu 20.04+ or any Debian-based distro |

---

---

# Configuración del Sistema

Configuración de máquina en un solo comando para Windows (CMD) y WSL. Instala **uv**, **git** y Python, registra el comando `system-setup`, y luego ofrece instalar de forma interactiva:

- Node.js
- MySQL
- PostgreSQL
- Claude Code CLI
- OpenAI Codex CLI
- VS Code

---

## Inicio rápido

### Windows (CMD) — ejecutar como Administrador

Abra el **Símbolo del sistema como Administrador** y ejecute:

```cmd
curl -fsSL https://raw.githubusercontent.com/charlar/system-setup/master/bootstrap.cmd -o bootstrap.cmd && bootstrap.cmd
```

O descargue `bootstrap.cmd` del repositorio y haga clic derecho → **Ejecutar como administrador**.

### WSL (Ubuntu / Debian)

Abra una **terminal WSL** y ejecute:

```bash
curl -fsSL https://raw.githubusercontent.com/charlar/system-setup/master/bootstrap.sh | bash
```

---

## Qué hace el bootstrap

1. Instala **Chocolatey** (Windows) o usa **apt** (WSL) como gestor de paquetes.
2. Instala **git** si no está disponible.
3. Instala **uv** (gestor de paquetes Python rápido) si no está disponible.
4. Clona este repositorio en `~/system-setup` (o actualiza si ya existe).
5. Usa `uv` para instalar la versión requerida de Python.
6. Ejecuta `uv tool install .` para registrar el comando `system-setup`.
7. Ejecuta `system-setup`, que verifica cada herramienta opcional y pregunta si desea instalarla.

---

## Volver a ejecutar la configuración

Tras el bootstrap inicial, ejecute desde cualquier terminal:

```cmd
system-setup
```

---

## Requisitos previos

| Plataforma | Requisito |
|------------|-----------|
| Windows    | Windows 10 / 11, privilegios de **Administrador** |
| WSL        | Ubuntu 20.04+ o cualquier distribución basada en Debian |
