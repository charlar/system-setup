"""
system-setupg — desktop window (pywebview) for installing/removing tools,
managing WSL + Docker, and editing PostgreSQL / MySQL saved connections.

The page (index.html + app.js) calls methods on `Api` directly through
window.pywebview.api — there is no web server or open port.
"""
import argparse
import logging
import os
import platform
import subprocess
import sys
import threading
import traceback
from importlib import resources
from importlib.metadata import PackageNotFoundError, version

from .. import myconfig, pgconfig, tools, updater, winenv, wsl
from ..jobs import JobRunner

IS_WINDOWS = platform.system() == "Windows"
HOME = os.path.expanduser("~")
LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", HOME), "system-setup")
log = logging.getLogger("system-setupg")


def _api(fn):
    """Wrap an Api method so JS always gets {ok, ...} instead of an exception."""
    def wrapper(self, *args, **kwargs):
        try:
            result = fn(self, *args, **kwargs)
            if isinstance(result, dict) and "ok" in result:
                return result
            return {"ok": True, "data": result}
        except Exception as e:
            log.error("%s failed:\n%s", fn.__name__, traceback.format_exc())
            return {"ok": False, "error": str(e)}
    wrapper.__name__ = fn.__name__
    return wrapper


def config_files() -> list[dict]:
    appdata = os.environ.get("APPDATA", HOME)
    entries = [
        ("PostgreSQL services", pgconfig.service_file(), "psql service=<name>"),
        ("PostgreSQL passwords", pgconfig.pgpass_file(), "host:port:db:user:password"),
        ("MySQL logins", myconfig.option_file(), "mysql --defaults-group-suffix=<name>"),
        ("Git config", os.path.join(HOME, ".gitconfig"), ""),
        ("SSH config", os.path.join(HOME, ".ssh", "config"), ""),
        ("npm config", os.path.join(HOME, ".npmrc"), ""),
        ("WSL settings (Windows side)", os.path.join(HOME, ".wslconfig"), "memory, CPUs, networking for all distros"),
        ("Claude Code settings", os.path.join(HOME, ".claude", "settings.json"), ""),
        ("Claude Code instructions", os.path.join(HOME, ".claude", "CLAUDE.md"), ""),
        ("Codex config", os.path.join(HOME, ".codex", "config.toml"), ""),
        ("VS Code settings", os.path.join(appdata, "Code", "User", "settings.json"), ""),
    ]
    return [{"label": l, "path": p, "exists": os.path.exists(p), "hint": h} for l, p, h in entries]


class Api:
    def __init__(self, selftest: bool = False):
        self._window = None
        self._jobs = JobRunner()
        self._selftest = selftest
        self._js_errors: list[str] = []
        self._update = None          # None = still checking
        threading.Thread(target=self._check_update, daemon=True).start()

    def _check_update(self):
        self._update = updater.update_available()

    # ---- app ----------------------------------------------------------------

    @_api
    def get_state(self):
        try:
            ver = version("system-setup")
        except PackageNotFoundError:
            ver = "dev"
        return {
            "version": ver,
            "admin": winenv.is_admin(),
            "windows": IS_WINDOWS,
            "update": self._update,
            "repo": updater.REPO_DIR,
            "busy": self._jobs.busy,
            "selftest": self._selftest,
        }

    @_api
    def restart_as_admin(self):
        if winenv.relaunch_elevated("system_setup.gui"):
            self._window.destroy()
            return True
        raise RuntimeError("Elevation was cancelled.")

    @_api
    def apply_update(self):
        if self._jobs.busy:
            raise RuntimeError("Wait for the running install to finish first.")
        ok, out = updater.pull()
        if not ok:
            raise RuntimeError(f"git pull failed:\n{out}")
        updater.schedule_reinstall(relaunch="system-setupg")
        threading.Timer(0.5, self._window.destroy).start()
        return out

    # ---- jobs ---------------------------------------------------------------

    def _start(self, title, steps):
        job = self._jobs.start(title, steps)
        return {"ok": True, "job": job.id}

    @_api
    def job_status(self, job_id, offset=0):
        job = self._jobs.get(int(job_id))
        if not job:
            raise ValueError("No such job")
        return {"id": job.id, "title": job.title, "state": job.state, "reboot": job.reboot,
                "lines": job.lines[offset:], "next": len(job.lines)}

    # ---- Windows tools --------------------------------------------------------

    @_api
    def get_tools(self):
        return tools.all_status()

    def _tool(self, tool_id):
        tool = tools.BY_ID.get(tool_id)
        if not tool:
            raise ValueError(f"Unknown tool {tool_id}")
        if tool.needs_admin and not winenv.is_admin():
            raise PermissionError("Chocolatey installs need administrator rights — click 'Restart as administrator'.")
        return tool

    @_api
    def install_tool(self, tool_id, password=""):
        tool = self._tool(tool_id)
        return self._start(f"Install {tool.name}", tools.install_steps(tool, password or ""))

    @_api
    def remove_tool(self, tool_id):
        tool = self._tool(tool_id)
        return self._start(f"Remove {tool.name}", tools.remove_steps(tool))

    # ---- WSL ----------------------------------------------------------------

    @_api
    def wsl_distros(self):
        return wsl.distros()

    @_api
    def wsl_info(self, name):
        return {"ok": True, "data": wsl.distro_info(name)}   # distro_info has its own 'ok' key

    @_api
    def wsl_install(self):
        if not winenv.is_admin():
            raise PermissionError("Installing WSL needs administrator rights.")
        wsl.install_wsl()
        return True

    @_api
    def docker_install(self, distro):
        return self._start(f"Install Docker Engine in {distro}", wsl.docker_install_steps(distro))

    @_api
    def docker_remove(self, distro, purge_data=False):
        return self._start(f"Remove Docker from {distro}", wsl.docker_remove_steps(distro, bool(purge_data)))

    @_api
    def apt(self, distro, action, packages):
        pkgs = packages.split() if isinstance(packages, str) else list(packages)
        return self._start(f"apt {action} {' '.join(pkgs)} ({distro})", wsl.apt_steps(distro, action, pkgs))

    # ---- PostgreSQL ------------------------------------------------------------

    @_api
    def pg_list(self):
        return {"ok": True, "data": pgconfig.list_services(),
                "files": [pgconfig.service_file(), pgconfig.pgpass_file()],
                "psql": pgconfig.find_psql() or ""}

    @_api
    def pg_save(self, data, old_name=None):
        pgconfig.save_service(data, old_name or None)
        return True

    @_api
    def pg_delete(self, name):
        pgconfig.delete_service(name)
        return True

    @_api
    def pg_test(self, name):
        ok, out = pgconfig.test_service(name)
        return {"ok": True, "success": ok, "output": out}

    # ---- MySQL -----------------------------------------------------------------

    @_api
    def my_list(self):
        return {"ok": True, "data": myconfig.list_logins(), "files": [myconfig.option_file()],
                "mysql": myconfig.find_mysql() or ""}

    @_api
    def my_save(self, data, old_name=None):
        myconfig.save_login(data, old_name)
        return True

    @_api
    def my_delete(self, name):
        myconfig.delete_login(name)
        return True

    @_api
    def my_test(self, name):
        ok, out = myconfig.test_login(name)
        return {"ok": True, "success": ok, "output": out}

    # ---- files -----------------------------------------------------------------

    @_api
    def get_files(self):
        return config_files()

    def _known(self, path):
        known = {os.path.normcase(f["path"]) for f in config_files()}
        if os.path.normcase(path) not in known:
            raise PermissionError("Not a known config file")
        return path

    @_api
    def edit_file(self, path):
        path = self._known(path)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "a").close()
        code = tools.find_exe(tools.BY_ID["vscode"])
        if code:
            subprocess.Popen(["cmd", "/c", code, path], creationflags=winenv.NO_WINDOW)
        else:
            subprocess.Popen(["notepad.exe", path])
        return True

    @_api
    def show_file(self, path):
        path = self._known(path)
        if os.path.exists(path):
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        else:
            folder = os.path.dirname(path)
            os.makedirs(folder, exist_ok=True)
            subprocess.Popen(["explorer.exe", folder])
        return True

    # ---- page lifecycle ---------------------------------------------------------

    def js_error(self, message):
        log.error("JS: %s", message)
        self._js_errors.append(str(message))

    def ready(self):
        """Called by the page once it has rendered and loaded the tool list."""
        log.info("page ready")
        if self._selftest:
            result = "SELFTEST OK" if not self._js_errors else "SELFTEST FAILED: " + " | ".join(self._js_errors)
            log.info(result)
            with open(os.path.join(LOG_DIR, "selftest.txt"), "w", encoding="utf-8") as f:
                f.write(result + "\n")
            threading.Timer(1.0, self._window.destroy).start()


def _setup_logging() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(LOG_DIR, "gui.log"), level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="system-setupg")
    parser.add_argument("--no-elevate", action="store_true", help="don't ask for administrator rights")
    parser.add_argument("--debug", action="store_true", help="enable the browser dev tools")
    parser.add_argument("--selftest", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    _setup_logging()

    if not IS_WINDOWS:
        print("system-setupg is a Windows app. Run it from Windows — it manages WSL from there.")
        sys.exit(1)

    if not args.no_elevate and not args.selftest and not winenv.is_admin():
        extra = ["--debug"] if args.debug else []
        if winenv.relaunch_elevated("system_setup.gui", extra + ["--no-elevate"]):
            return
        log.info("elevation declined; running without admin")

    import webview

    winenv.refresh_path()
    api = Api(selftest=args.selftest)
    page = resources.files("system_setup.gui").joinpath("web", "index.html")
    window = webview.create_window(
        "System Setup", url=str(page), js_api=api,
        width=1120, height=780, min_size=(860, 560),
    )
    api._window = window
    log.info("starting window (admin=%s)", winenv.is_admin())
    webview.start(debug=args.debug)
