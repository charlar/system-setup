#!/usr/bin/env bash
# Install Docker Engine inside a WSL distro (Ubuntu/Debian), run as root.
# Usage: bash docker_wsl.sh <linux-user-to-add-to-docker-group>
# Follows https://docs.docker.com/engine/install/ubuntu/ (deb822 .sources file).
set -euo pipefail
TARGET_USER="${1:-}"
export DEBIAN_FRONTEND=noninteractive

. /etc/os-release
case "$ID" in
    ubuntu|debian) ;;
    *) echo "Unsupported distro '$ID' — only Ubuntu and Debian are supported."; exit 1 ;;
esac
CODENAME="${UBUNTU_CODENAME:-$VERSION_CODENAME}"

echo "--- Removing conflicting packages (if any)"
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then apt-get remove -y "$pkg"; fi
done

echo "--- Adding Docker's apt repository ($ID $CODENAME)"
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
rm -f /etc/apt/sources.list.d/docker.list
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/$ID
Suites: $CODENAME
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

echo "--- Installing Docker Engine"
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != "root" ]; then
    echo "--- Adding $TARGET_USER to the docker group (no sudo needed for docker)"
    usermod -aG docker "$TARGET_USER"
fi

echo "--- Checking systemd"
if grep -Eqs '^\s*systemd\s*=\s*true' /etc/wsl.conf; then
    echo "systemd already enabled in /etc/wsl.conf"
else
    touch /etc/wsl.conf
    sed -i -E '/^\s*systemd\s*=/d' /etc/wsl.conf
    if grep -qs '^\[boot\]' /etc/wsl.conf; then
        sed -i '/^\[boot\]/a systemd=true' /etc/wsl.conf
    else
        printf '\n[boot]\nsystemd=true\n' >> /etc/wsl.conf
    fi
    echo "Enabled systemd in /etc/wsl.conf"
fi

if [ "$(ps -p 1 -o comm= 2>/dev/null)" = "systemd" ]; then
    systemctl enable --now docker
    docker --version
else
    # The GUI watches for this marker and restarts the distro
    echo "@@RESTART_WSL@@"
fi
