"""
WSL management from the Windows side. Everything goes through wsl.exe;
`wsl -u root` gives root inside the distro without a Linux password, so
Docker/apt installs don't need sudo prompts.
"""
import os
import re
import subprocess
from importlib import resources

from .i18n import t
from .jobs import Job, Step, run_cmd
from .winenv import NO_WINDOW

# Docker's official packages, plus Ubuntu's own docker.io family
DOCKER_PKGS = ["docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin",
               "docker-compose-plugin", "docker-ce-rootless-extras",
               "docker.io", "docker-compose-v2", "docker-buildx", "containerd", "runc"]
APT_NAME = re.compile(r"^[a-z0-9][a-z0-9+.\-]*$")


def _env() -> dict:
    return dict(os.environ, WSL_UTF8="1")


def _decode(b: bytes) -> str:
    # wsl.exe's own messages are UTF-16 unless WSL_UTF8 is honored (older builds)
    if b[:2] in (b"\xff\xfe",) or (len(b) > 1 and b[1:2] == b"\x00"):
        try:
            return b.decode("utf-16-le").lstrip("﻿")
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace").replace("\x00", "")


def _wsl(args: list[str], stdin: str | None = None, timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["wsl.exe", *args],
            input=stdin.replace("\r\n", "\n").encode() if stdin is not None else None,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True, timeout=timeout, env=_env(), creationflags=NO_WINDOW,
        )
        return r.returncode, _decode(r.stdout + r.stderr)
    except FileNotFoundError:
        return -1, "wsl.exe not found"
    except subprocess.TimeoutExpired:
        return -2, "timed out"


def _sh(distro: str, script: str, user: str | None = None, timeout: int = 60) -> tuple[int, str]:
    args = ["-d", distro] + (["-u", user] if user else []) + ["--", "sh", "-s"]
    return _wsl(args, stdin=script, timeout=timeout)


def distros() -> dict:
    """{'installed': bool, 'distros': [{name, state, version, default}], 'message': str}"""
    code, out = _wsl(["-l", "-v"], timeout=30)
    if code == -1:
        return {"installed": False, "distros": [], "message": t("wsl.not_installed")}
    result = []
    for line in out.splitlines()[1:]:
        line = line.rstrip()
        if not line.strip():
            continue
        default = line.lstrip().startswith("*")
        parts = line.replace("*", " ", 1).split()
        if len(parts) >= 3 and not parts[0].startswith("docker-desktop"):
            result.append({"name": " ".join(parts[:-2]), "state": parts[-2],
                           "version": parts[-1], "default": default})
    if code != 0 and not result:
        return {"installed": False, "distros": [], "message": out.strip() or t("wsl.no_distros")}
    return {"installed": True, "distros": result, "message": ""}


INFO_SCRIPT = r"""
echo "user=$(whoami)"
. /etc/os-release 2>/dev/null; echo "os=$PRETTY_NAME"; echo "id=$ID"
echo "systemd=$( [ "$(ps -p 1 -o comm= 2>/dev/null)" = systemd ] && echo yes || echo no)"
echo "docker=$(docker --version 2>/dev/null)"
echo "compose=$(docker compose version 2>/dev/null)"
# old standalone Compose v1 (docker-compose with a hyphen)
echo "compose_v1=$(docker-compose version --short 2>/dev/null)"
echo "active=$(systemctl is-active docker 2>/dev/null)"
echo "pkg=$(dpkg -s docker-ce >/dev/null 2>&1 && echo "docker-ce (Docker's official repo)" || { dpkg -s docker.io >/dev/null 2>&1 && echo "docker.io (Ubuntu's package)"; })"
echo "ingroup=$(id -nG 2>/dev/null | tr ' ' '\n' | grep -qx docker && echo yes || echo no)"
echo "desktop=$(readlink -f "$(command -v docker 2>/dev/null)" 2>/dev/null | grep -qi 'docker desktop\|/mnt/' && echo yes || echo no)"
"""


def distro_info(name: str) -> dict:
    code, out = _sh(name, INFO_SCRIPT, timeout=90)
    info = {"name": name, "ok": code == 0, "error": "" if code == 0 else out.strip()}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k.strip()] = v.strip()
    return info


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def _docker_script() -> str:
    return resources.files("system_setup").joinpath("scripts/docker_wsl.sh").read_text(encoding="utf-8")


def docker_install_steps(distro: str) -> list[Step]:
    def find_user(job: Job) -> bool:
        code, out = _sh(distro, "whoami")
        user = out.strip().splitlines()[-1] if code == 0 and out.strip() else ""
        if not user:
            job.log(t("log.wsl_start_failed", distro=distro, error=out.strip()))
            return False
        job.data["user"] = user
        job.log(t("log.wsl_user", user=user))
        return True

    def run_script(job: Job) -> bool:
        step = Step(["wsl.exe", "-d", distro, "-u", "root", "--", "bash", "-s", "--", job.data["user"]],
                    stdin=_docker_script(), display=f"wsl -d {distro} -u root -- bash docker_wsl.sh {job.data['user']}")
        start = len(job.lines)
        ok = run_cmd(job, step)
        job.data["restart"] = any("@@RESTART_WSL@@" in l for l in job.lines[start:])
        return ok

    def restart_if_needed(job: Job) -> bool:
        if not job.data.get("restart"):
            return True
        job.log(t("log.wsl_restart", distro=distro))
        if not run_cmd(job, Step(["wsl.exe", "--terminate", distro])):
            return False
        return run_cmd(job, Step(["wsl.exe", "-d", distro, "-u", "root", "--", "sh", "-s"],
                                 stdin="systemctl enable --now docker && docker --version\n",
                                 display=f"wsl -d {distro} -u root -- systemctl enable --now docker"))

    def verify(job: Job) -> bool:
        ok = run_cmd(job, Step(["wsl.exe", "-d", distro, "-u", "root", "--", "sh", "-s"],
                               stdin="docker run --rm hello-world\n",
                               display=f"wsl -d {distro} -u root -- docker run --rm hello-world"))
        if ok:
            job.log(t("log.docker_ok", distro=distro))
        return ok

    return [Step(call=find_user), Step(call=run_script), Step(call=restart_if_needed), Step(call=verify)]


def docker_remove_steps(distro: str, purge_data: bool = False) -> list[Step]:
    script = (
        "set -e\nexport DEBIAN_FRONTEND=noninteractive\n"
        "systemctl stop docker docker.socket containerd 2>/dev/null || true\n"
        # purge only what's installed — unknown package names make apt fail
        f"PKGS=''\nfor p in {' '.join(DOCKER_PKGS)}; do dpkg -s \"$p\" >/dev/null 2>&1 && PKGS=\"$PKGS $p\" || true; done\n"
        "if [ -n \"$PKGS\" ]; then apt-get purge -y $PKGS; else echo 'No Docker packages installed.'; fi\n"
        "apt-get autoremove -y\n"
        "rm -f /etc/apt/sources.list.d/docker.sources /etc/apt/sources.list.d/docker.list /etc/apt/keyrings/docker.asc\n"
    )
    if purge_data:
        script += "rm -rf /var/lib/docker /var/lib/containerd\n"

    def done(job: Job) -> bool:
        job.log(t("log.docker_data_deleted") if purge_data else t("log.docker_data_kept"))
        return True

    return [Step(["wsl.exe", "-d", distro, "-u", "root", "--", "bash", "-s"], stdin=script,
                 display=f"wsl -d {distro} -u root -- apt-get purge docker-ce ..."),
            Step(call=done)]


def apt_steps(distro: str, action: str, packages: list[str]) -> list[Step]:
    pkgs = [p.strip().lower() for p in packages if p.strip()]
    if not pkgs:
        raise ValueError(t("err.apt_empty"))
    bad = [p for p in pkgs if not APT_NAME.match(p)]
    if bad:
        raise ValueError(t("err.apt_bad", names=", ".join(bad)))
    if action not in ("install", "remove"):
        raise ValueError("action must be install or remove")
    script = "set -e\nexport DEBIAN_FRONTEND=noninteractive\n"
    if action == "install":
        script += f"apt-get update\napt-get install -y {' '.join(pkgs)}\n"
    else:
        script += f"apt-get remove -y {' '.join(pkgs)}\napt-get autoremove -y\n"
    return [Step(["wsl.exe", "-d", distro, "-u", "root", "--", "bash", "-s"], stdin=script,
                 display=f"wsl -d {distro} -u root -- apt-get {action} -y {' '.join(pkgs)}")]


def install_wsl() -> None:
    """`wsl --install` may prompt and usually needs a reboot, so give it its own console."""
    subprocess.Popen(["wsl.exe", "--install", "-d", "Ubuntu"], creationflags=subprocess.CREATE_NEW_CONSOLE)
