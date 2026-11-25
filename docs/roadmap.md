# Roadmap and future improvements

## Next: v0.3

- Apps as plugins, a data-only catalog, and a filtered Apps screen with slide-over
  configuration panels. See [plugin-plan.md](plugin-plan.md).

## Ideas

- **Reset a forgotten root password** (PostgreSQL / MySQL) from the GUI. Needs a
  server restart in a special mode (`trust` in `pg_hba.conf`; `--skip-grant-tables`
  or `--init-file` for MySQL), so it must be careful and clearly confirmed.
- **Upgrades**: show outdated choco packages and upgrade them (part of the v0.3 Updates filter).
- **More WSL tools** beyond Docker (apt packages as catalog entries).

## Not yet tested on a real machine (v0.2.0)

Covered by unit-style tests and the GUI self-test, but not yet run end to end:

- Real Chocolatey installs and removals from the GUI
- Docker install in WSL (`scripts/docker_wsl.sh`) on a fresh distro
- A standard (non-admin) Windows account: per-install UAC prompts
- `wsl --install` from the GUI
- MySQL install with a password, and Change password against a real server
- Self-update from one tag to the next (Releases channel)
- The full bootstrap on a clean PC

Report problems as GitHub issues.
