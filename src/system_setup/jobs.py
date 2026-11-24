"""
Background job runner: runs a list of steps (commands or Python callables) in a
thread and collects output so the GUI can poll it. One job at a time — choco
and apt both hold locks, so parallel installs would just fail anyway.
"""
import itertools
import json
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .i18n import t
from . import winenv
from .winenv import IS_WINDOWS, NO_WINDOW, refresh_path

# choco: 1641 / 3010 = success, reboot required
REBOOT_CODES = {1641, 3010}


@dataclass
class Step:
    argv: list[str] | None = None
    display: str = ""                 # what to show in the log instead of argv (hides secrets)
    stdin: str | None = None          # text piped to the process (e.g. a bash script for wsl)
    env: dict[str, str] | None = None
    ok_codes: tuple[int, ...] = (0,)
    call: Callable[["Job"], bool] | None = None   # Python step; return False to fail the job
    allow_fail: bool = False
    elevated: bool = False            # needs admin: run through UAC if we aren't elevated


@dataclass
class Job:
    id: int
    title: str
    steps: list[Step]
    lines: list[str] = field(default_factory=list)
    state: str = "running"            # running | ok | failed
    reboot: bool = False
    data: dict = field(default_factory=dict)   # scratch space shared between steps
    started: float = field(default_factory=time.time)

    def log(self, text: str) -> None:
        for line in text.splitlines() or [""]:
            self.lines.append(line)


class JobRunner:
    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self._jobs: dict[int, Job] = {}
        self._lock = threading.Lock()
        self.on_finish: Callable[[Job], None] | None = None

    @property
    def busy(self) -> bool:
        return any(j.state == "running" for j in self._jobs.values())

    def start(self, title: str, steps: list[Step]) -> Job:
        with self._lock:
            if self.busy:
                raise RuntimeError(t("job.busy"))
            job = Job(next(self._ids), title, steps)
            self._jobs[job.id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def get(self, job_id: int) -> Job | None:
        return self._jobs.get(job_id)

    def current(self) -> Job | None:
        return next((j for j in self._jobs.values() if j.state == "running"), None)

    # ------------------------------------------------------------------

    def _run(self, job: Job) -> None:
        job.log(f"=== {job.title} ===")
        ok = True
        try:
            for step in job.steps:
                if step.call:
                    good = bool(step.call(job))
                else:
                    good = run_cmd(job, step)
                if not good and not step.allow_fail:
                    ok = False
                    break
        except Exception as e:   # never leave a job stuck in 'running'
            job.log(f"[error] {e}")
            ok = False
        refresh_path()
        job.state = "ok" if ok else "failed"
        job.log("")
        job.log(t("job.ok") if ok else t("job.failed"))
        if job.reboot:
            job.log(t("job.reboot"))
        if self.on_finish:
            try:
                self.on_finish(job)
            except Exception:
                pass


def _finish(job: Job, step: Step, code: int) -> bool:
    if code in REBOOT_CODES:
        job.reboot = True
        return True
    if code not in step.ok_codes:
        job.log(f"[exit code {code}]")
        return False
    return True


def _append_output(job: Job, data: bytes) -> None:
    for raw in data.splitlines():
        text = raw.decode("utf-8", errors="replace").replace("\x00", "")
        job.lines.append(text.split("\r")[-1])


def run_elevated(job: Job, step: Step) -> bool:
    """Run step.argv through UAC via system_setup.elevated, tailing its log file."""
    tmp = tempfile.mkdtemp(prefix="system-setup-")
    log_path = os.path.join(tmp, "output.log")
    spec_path = os.path.join(tmp, "spec.json")
    open(log_path, "wb").close()
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump({"argv": step.argv, "log": log_path}, f)
    job.log(t("log.elevating"))
    try:
        try:
            handle = winenv.start_elevated_helper(spec_path)
        except winenv.ElevationCancelled:
            job.log(t("log.elevation_cancelled"))
            return False
        pos, pending = 0, b""
        code = None
        while code is None:
            code = winenv.wait_handle(handle, 300)
            with open(log_path, "rb") as f:
                f.seek(pos)
                chunk = f.read()
            pos += len(chunk)
            data = pending + chunk
            # only emit complete lines until the process is done
            cut = data.rfind(b"\n") + 1 if code is None else len(data)
            _append_output(job, data[:cut])
            pending = data[cut:]
        return _finish(job, step, code)
    finally:
        for p in (spec_path, log_path):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def run_cmd(job: Job, step: Step) -> bool:
    refresh_path()
    job.log(f"> {step.display or subprocess.list2cmdline(step.argv)}")
    if step.elevated and IS_WINDOWS and not winenv.is_admin():
        return run_elevated(job, step)
    env = dict(os.environ, WSL_UTF8="1", PYTHONIOENCODING="utf-8")
    if step.env:
        env.update(step.env)
    try:
        proc = subprocess.Popen(
            step.argv,
            stdin=subprocess.PIPE if step.stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, creationflags=NO_WINDOW,
        )
    except FileNotFoundError:
        job.log(t("job.not_found", cmd=step.argv[0]))
        return False
    if step.stdin is not None:
        # write stdin from a thread so a chatty process can't deadlock us
        def feed():
            try:
                proc.stdin.write(step.stdin.replace("\r\n", "\n").encode("utf-8"))
                proc.stdin.close()
            except OSError:
                pass
        threading.Thread(target=feed, daemon=True).start()
    assert proc.stdout
    for raw in iter(proc.stdout.readline, b""):
        text = raw.decode("utf-8", errors="replace").replace("\x00", "").rstrip("\r\n")
        # progress bars redraw with \r — keep only the final state of the line
        text = text.split("\r")[-1]
        job.lines.append(text)
    return _finish(job, step, proc.wait())
