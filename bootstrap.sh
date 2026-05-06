#!/usr/bin/env bash
# Bootstrap script for WSL — installs uv, git, clones the repo, and runs setup.py
set -euo pipefail

REPO_URL="https://github.com/charlar/system-setup.git"
REPO_DIR="$HOME/system-setup"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warning() { echo -e "${YELLOW}[setup]${NC} $*"; }

# ---------- git ----------
if command -v git &>/dev/null; then
    info "git already installed / git ya está instalado ($(git --version))"
else
    info "Installing git / Instalando git..."
    sudo apt-get update -qq
    sudo apt-get install -y git
fi

# ---------- uv ----------
UV_BIN="$HOME/.local/bin/uv"

if command -v uv &>/dev/null || [ -x "$UV_BIN" ]; then
    UV_CMD=$(command -v uv 2>/dev/null || echo "$UV_BIN")
    info "uv already installed / uv ya está instalado ($($UV_CMD --version))"
    export PATH="$HOME/.local/bin:$PATH"
else
    info "Installing uv / Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    source "$HOME/.local/bin/env" 2>/dev/null || true
fi

# ---------- clone / update repo ----------
if [ -d "$REPO_DIR/.git" ]; then
    info "Repository already cloned — pulling latest / Repositorio ya clonado — actualizando..."
    git -C "$REPO_DIR" pull --ff-only
else
    info "Cloning repository / Clonando repositorio..."
    git clone "$REPO_URL" "$REPO_DIR"
fi

# ---------- Python via uv ----------
cd "$REPO_DIR"
info "Ensuring Python is available / Verificando que Python esté disponible..."
uv python install

# ---------- run setup ----------
info "Running setup / Ejecutando configuración..."
uv run setup.py
