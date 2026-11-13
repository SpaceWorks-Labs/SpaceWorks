---
title: Update and re-run the installer
summary: Update to a new release, change modules, or toggle web access to the control plane from the installer menu.
order: 20
keywords: update, upgrade, release, installer menu, rollback, runner, github actions, modules, version
---
## The installer menu

Running the installer again on an installed server offers a menu instead of first-time setup:

1. Update to the latest release.
2. Change modules only.
3. Update, then change modules.
4. Cancel (the default).
5. Install or re-register the automatic update runner.
6. Turn web access to the control plane on or off.

## Update by hand

Run `scripts/update.sh`. It takes a lock, saves a database dump to `backups/`, pulls the pinned images, runs migrations and waits until the app reports ready. To pin a version, pass it with `--version`.

![Screenshot: an update finishing with the readiness check](screenshot:op-update)

If an update fails, the app images roll back, but database migrations that ran stay applied. The pre-update dump holds the database only (no uploaded files) and is kept for 14 days.

## Automatic updates

Install the runner with option 5, then switch automatic deployment on in your repository settings. Lock down the runner first: it can deploy to your server.

> **Who can do this:** the host operator.
