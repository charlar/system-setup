# Plan: reliable updates with rollback

Status: proposed, not started.

## Why

Today an update changes `~/system-setup` (a git clone) in place, then reinstalls from it
with `uv tool install`. That broke on v0.1.0: an untracked `uv.lock` in the clone
blocked `git pull`, the failure was ignored, and every launch offered the same update
again. The underlying problems:

- **The working copy is the install source.** Anything left in it (stray files,
  edits, a half-finished checkout) can block or corrupt the next update.
- **Failures are silent.** The reinstall runs in a hidden batch file after the app
  exits; nobody sees its output, and nothing checks that it worked.
- **No way back.** Once the clone has moved and the reinstall fails, or the new
  version is broken, there's no previous version to return to.

## Layout

Everything lives in one app-owned folder that people don't work in:

```
%LOCALAPPDATA%\system-setup\          (~/.local/share/system-setup on WSL)
  repo.git\                            bare mirror of GitHub: fetch only, no working tree
  versions\
    v0.2.0\system_setup-0.2.0-py3-none-any.whl
    v0.3.0\system_setup-0.3.0-py3-none-any.whl
  versions.json                        current, previous, and when each was installed
  update.log                           every update, rollback and deletion, with output
  gui.log                              (already here)
```

- **`repo.git`** is a bare repository (`git clone --mirror`). With no working tree,
  there are no stray files to block anything. Updates only `git fetch` into it.
- **One folder per version, holding a built wheel.** A new version is exported with
  `git archive <tag>` into a temp folder, built with `uv build --wheel`, and only the
  wheel is kept (about 100 KB). Version folders never change after they're created.
- **Installing a version** = `uv tool install versions\vX\*.whl --reinstall`. Rolling
  back is the same command with an older wheel.
- On the Latest channel, folders are named after the commit: `versions\master-abc1234`.

## Update steps

1. **Check** (on launch, in the background, as now): `git fetch` into `repo.git` and
   compare tags with the installed version.
2. **Stage** while the app keeps running: export, build the wheel, and put it in
   `versions\vX`. If the build fails, report it in the banner and leave the current
   install untouched.
3. **Swap** after the app exits (Windows locks the running `.exe`): a small script
   reinstalls from the staged wheel, retrying while the exe is locked (as now). The
   script writes all output to `update.log`.
4. **Verify**: the script runs `system-setup --version` (a new flag) and checks it
   prints the new version. That also proves the package imports.
5. **Automatic rollback**: if the reinstall or the check fails, the script reinstalls
   the previous wheel and records the failure in `versions.json`.
6. **Report**: on the next launch, a one-time banner says either "Updated to v0.3.0"
   or "The update to v0.3.0 failed, so you're still on v0.2.0", with a link to
   `update.log`.

Most of the work moves into step 2, while the app is still running and can show
errors. Step 3 then only has to reinstall a wheel that is already built.

## Rollback and deletion

A **Versions** panel, next to the Updates switch:

| Version | Installed | |
| --- | --- | --- |
| v0.3.0 (current) | 2026-12-02 | |
| v0.2.0 | 2026-11-24 | **Roll back** · **Delete** |

- **Roll back**: confirm, then the same swap, verify and report steps as an update,
  using the older wheel.
- **Delete**: removes that version's folder. The current version can't be deleted.
- **Delete all old versions**: one button to free the space.
- **Keep**: by default the current version plus the previous one; older versions are
  deleted automatically after a successful update. Configurable in `settings.ini`
  (`keep_versions = 2`).
- After a rollback, update checks skip the version you rolled back from, so the banner
  doesn't immediately offer it again. A newer version is offered as usual.

From the command line:

```
system-setup --versions               list installed versions
system-setup --rollback [version]     default: the previous one
system-setup --delete-version <ver>
system-setup --version
```

## Things to watch

- **Dependencies on rollback**: reinstalling a wheel resolves its dependencies
  (pywebview) again. uv's cache normally has them; with no cache and no network a
  rollback can fail. That's acceptable, and it is logged.
- **Settings compatibility**: an older version must still read a newer
  `settings.ini`. Rule from now on: only add keys, ignore unknown ones, never change the
  meaning of an existing key.
- **The swap script can't use the app's own Python**, because its virtual environment
  is the thing being replaced. Keep it a batch file on Windows (shell script on WSL),
  with the same no-labels rule as the bootstrap.
- **Jobs in progress**: the existing guard stays: no update or rollback while an
  install is running.

## Migration

- **Bootstrap**: new installs create `repo.git` and the first version folder directly.
  The bootstrap stops cloning to `~/system-setup`.
- **Existing installs**: the first launch of the new version converts the install. It
  creates `repo.git` (fetched from GitHub, using the clone's objects when they're
  available), adds a version folder for the current version, and records it in
  `versions.json`. `~/system-setup` is then no longer used. The app says so once and
  offers to delete it, but doesn't delete it on its own, in case someone has work there.
- **The fix-update scripts** keep using `~/system-setup`. Their job is to move a stuck
  v0.1.0 install to the newest release, which then converts itself.

## Shipping

Release this as **v0.2.1, before v0.3**. Then v0.3, which is large, is the first
update delivered by the new system, and can be rolled back if the plugin rework
breaks something. v0.2.0 installs reach v0.2.1 with the old updater, which works now
that `uv.lock` is tracked.

## Tests

- Unit: tag selection, `versions.json` reads and writes, the retention rule, refusing
  to delete the current version.
- A local run through: build two wheels from two tags, update, roll back, delete, and
  check `uv tool list` at each step.
- Failure injection: a wheel that fails to build (nothing changes), a wheel whose
  import fails (automatic rollback), the exe still locked (retry, then rollback and
  report).
- End to end on a real machine: v0.2.0 → v0.2.1 (migration), then v0.2.1 → v0.2.2 and
  back.
