#!/usr/bin/env bash
# One-time fix for installs stuck on v0.1.0: its updater says a new version is
# available but never installs it (a stray uv.lock in the clone blocks git pull).
# Moves ~/system-setup to the newest release and reinstalls.
# Newer versions update themselves.
set -euo pipefail

REPO_DIR="$HOME/system-setup"
export PATH="$HOME/.local/bin:$PATH"

info()  { echo -e "\033[0;32m[fix]\033[0m $*"; }
fail()  { echo -e "\033[0;31m[fix] ERROR:\033[0m $*" >&2; exit 1; }

[ -d "$REPO_DIR/.git" ] || fail "System Setup is not installed — run bootstrap.sh instead / System Setup no está instalado — ejecute bootstrap.sh"

git config --global --add safe.directory "$REPO_DIR"
info "Fetching releases / Descargando versiones..."
git -C "$REPO_DIR" fetch origin --tags --force --quiet

TAG=$(git -C "$REPO_DIR" tag --list 'v*' --sort=-v:refname | head -n1)
[ -n "$TAG" ] || fail "No release found / No se encontró ninguna versión"

info "Switching to $TAG / Cambiando a $TAG..."
git -C "$REPO_DIR" -c advice.detachedHead=false checkout --quiet --force --detach "$TAG"

info "Reinstalling / Reinstalando..."
uv tool install "$REPO_DIR" --reinstall

info "Done — System Setup is now $TAG / Listo — System Setup ahora es $TAG"
