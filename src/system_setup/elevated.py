"""
Runs ONE command with administrator rights on behalf of system-setupg.

The GUI runs as the normal user (so config files stay in their own profile)
and starts this module through UAC only for steps that need admin, like
choco installs. UAC can't pipe output back to a non-elevated parent, so:

  pythonw -m system_setup.elevated <spec.json>
    spec: {"argv": [...], "log": "<path>"}

The spec is deleted as soon as it's read (it can contain a database password),
output goes to the log file (the GUI tails it), and the exit code is ours.
"""
import json
import os
import subprocess
import sys

from .winenv import NO_WINDOW


def main() -> int:
    spec_path = sys.argv[1]
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    try:
        os.remove(spec_path)
    except OSError:
        pass
    with open(spec["log"], "ab", buffering=0) as log:
        try:
            proc = subprocess.run(
                spec["argv"], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=NO_WINDOW,
            )
            return proc.returncode
        except OSError as e:
            log.write(f"[error] {e}\n".encode("utf-8"))
            return 1


if __name__ == "__main__":
    sys.exit(main())
