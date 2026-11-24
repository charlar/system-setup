"""
Background job runner: runs a list of steps (commands or Python callables) in a
thread and collects output so the GUI can poll it. One job at a time — choco
and apt both hold locks, so parallel installs would just fail anyway.
"""
import itertools
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .winenv import NO_WINDOW, refresh_path

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
                raise RuntimeError("Another install is still running — wait for it to finish.")
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
        job.log("=== Finished successfully ===" if ok else "=== Failed ===")
        if job.reboot:
            job.log("A reboot is required to finish this install.")
        if self.on_finish:
            try:
                self.on_finish(job)
            except Exception:
                pass


def run_cmd(job: Job, step: Step) -> bool:
    refresh_path()
    job.log(f"> {step.display or subprocess.list2cmdline(step.argv)}")
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
        job.log(f"[error] command not found: {step.argv[0]}")
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
    code = proc.wait()
    if code in REBOOT_CODES:
        job.reboot = True
        return True
    if code not in step.ok_codes:
        job.log(f"[exit code {code}]")
        return False
    return True
