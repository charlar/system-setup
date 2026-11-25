# Plan: apps as plugins (v0.3)

Status: agreed direction, not started.

## Why

Today one app is spread over several places. PostgreSQL, for example:

- install/remove/post-install in `tools.py`
- a second, separate catalog in the CLI (`TOOLS` in `__init__.py`)
- configuration in `pgconfig.py`
- its own hard-coded tab in `gui/web/index.html`, `app.js` and `i18n.js`

Goal: each app's installation **and** configuration live in one place, shared by
the desktop app and the command line.

## Plugins

One folder per app, e.g. `system_setup/apps/postgresql/`:

| Part | Contents |
| --- | --- |
| Metadata | name, description, category, choco package, Windows or WSL, dependencies (Codex → Node) |
| Detect | installed? which version? |
| Install / remove | steps, plus post-install (e.g. PostgreSQL password) |
| Config (optional) | what can be configured, described as data, not screens |
| Strings | English and Spanish text |

The app discovers the folders at startup. CLI and GUI both read the same list,
which removes the duplicated catalog.

## Built-ins and "get more"

- **Built-in plugins** carry Python code: Git, Node, PostgreSQL, MySQL, Docker in WSL.
  They need real logic (post-install steps, passwords, config editors).
- **Catalog plugins** are data only: a small manifest (name, description, choco
  package, how to detect, dependencies). Enough for most apps: VS Code, gh, 7-Zip,
  Postman, DBeaver…
- **Never download executable code.** Installs run as administrator; a downloaded
  manifest can only say "install this choco package".
- The catalog lives in a `catalog/` folder in this repo and follows the update
  channel: Releases users read it from the newest tag, Latest users from `master`.
  Adding an app for everyone = committing one small file, no release needed.

## UI

- **Apps** screen with filters: **Installed / Available / Updates** (`choco outdated`),
  search, maybe categories (Languages, Databases, Editors, Containers).
- Clicking an **installed** app slides over to its configuration panel (back arrow):
  - PostgreSQL: services, passwords, Change password
  - MySQL: logins
  - Docker: the WSL card
  - anything else: a **generic panel** with version, Upgrade, Remove, install
    location and config-file links
- Clicking an app that **isn't installed** slides over to an install panel:
  description, what it pulls in, options (e.g. PostgreSQL password).
- Sidebar shrinks to **Apps / WSL / Settings**. The PostgreSQL, MySQL and Files tabs go away.

## Config screens as data

PostgreSQL services and MySQL logins share one shape: a list of saved entries,
fields (host, port, user, password, database), actions (Test, Change password,
Delete). One generic "saved connections" renderer can draw both from a
description. Odd cases (Docker in WSL) keep an optional custom panel.

## Order of work

1. Mockup of the Apps list and slide-over panel.
2. Plugin interface; move the existing apps into it (behavior unchanged).
3. Generic config renderer; move PostgreSQL/MySQL onto it.
4. Data-only catalog + download.
5. Updates filter (`choco outdated` / `choco upgrade`).
