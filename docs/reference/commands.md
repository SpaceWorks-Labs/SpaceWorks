---
title: Commands
group: Reference
order: 10
summary: The developer script, installer and updater options, host scripts and the management commands operators use.
---

# Commands

Where a command runs matters. Developer commands run from a repository checkout with Docker and Bash. Operator scripts run from the install directory on the server. `manage.py` commands run inside the backend container.

## Running `manage.py`

| Where | Form |
| --- | --- |
| Production install | `scripts/spaceworks-compose.sh bundled run --rm backend --role management python manage.py <command>` |
| Development stack | `./scripts/dev.sh exec backend python manage.py <command>` |

## Developer script: `scripts/dev.sh`

The single developer entry point. Needs Docker and Bash (Git Bash on Windows).

| Subcommand | What it does |
| --- | --- |
| `up [args]` | Compose up in the background, retire the live helper and remove successful one-shot containers. Add `--build` to rebuild |
| `down [args]` | Compose down. Volumes persist unless you pass `-v` |
| `test [args]` | Pytest in disposable Postgres, Redis and MinIO. Default argument is `-q` |
| `affected [backend or frontend]` | Only the tests for what changed |
| `e2e [args]` | Seed the running dev stack and run Playwright against a production preview |
| `hooks` | Enable the repository's git hooks (`.githooks/pre-push`) |
| anything else | Forwarded to Compose: `logs`, `exec`, `run`, `ps`, `restart` |

## Installer menu (rerun the installer on an existing install)

| Option | What it does |
| --- | --- |
| 1 | Update to this release (backs up the database first) |
| 2 | Change which areas are switched on |
| 3 | Update, then change areas |
| 4 | Cancel and change nothing |
| 5 | Set up automatic deploys (GitHub runner) |
| 6 | Turn web access to the control panel (`/control/`) on or off |
| 7 | Change outside services (database, Redis, storage, email) |

## Installer options

`curl -fsSL .../install.sh | sh -s -- <options>`

| Option | What it does |
| --- | --- |
| `--dry-run` | Checks and plan only |
| `--version X.Y.Z` | Install that published release (0.12.0 or newer); never older than installed |
| `--frontend full` or `api-only` | Answer the frontend question up front |
| `--repo owner/name` | Install and update from a fork |
| `--non-interactive --answers-file <file>` | Unattended install from a private (mode 0600) JSON file |
| `--resume` | Continue a verified incomplete install |
| `--profile free` | The opt-in free single-process profile |
| `--uninstall` [`--purge`] | Remove services and managed files; `--purge` also deletes local volumes after confirmation |
| `--help` | Print every option |

## Host scripts

Run as the install owner from the install directory.

| Script | Purpose |
| --- | --- |
| `scripts/update.sh` | Update. Options: `--force`, `--version <release>`, `--modules`, `--modules-only`, `--all-modules`, `--areas=a,b`, `--without=k1,k2`, `--makerspace <slug>`, `--all-makerspaces`, `--confirm-removals`, `--no-module-changes`, `--override-lock` |
| `scripts/update-rollback.sh` | Restart the previous application images after a failed update (called by the updater) |
| `scripts/install-runner.sh` | Install, re-register or (`--remove`) remove the GitHub Actions deploy runner |
| `scripts/control-plane-settings.sh` | Interactive control-plane access settings |
| `scripts/apply-settings.sh` | Apply an edited `.env` without changing release. `--control-plane on\|off [--allow-cidrs "..."] [--tunnel-port N]` |
| `scripts/switch-services.sh` | Move the database, Redis, storage or email outside or back |
| `scripts/import-backup.sh <archive> <superadmin> [sha256]` | Register a whole-deployment archive for restore |
| `scripts/restore.sh <restore-id>` | Run the disaster restore (add `--replace` for an outside database) |
| `scripts/uninstall.sh` | Uninstall |
| `scripts/spaceworks-compose.sh` | Compose wrapper for the install (`bundled` or outside-database shapes, `--profile tls`) |

## Management commands (`manage.py`)

### Setup and areas

| Command | Purpose |
| --- | --- |
| `setup_instance` | Create the first superadmin and makerspace |
| `list_modules`, `install_module <key>`, `uninstall_module <key>` | Show or switch modules for a space (`--makerspace <slug>`). Uninstall keeps data |
| `purge_module_data <key>` | Delete an uninstalled module's data (`--list`, `--makerspace`); superadmin, irreversible |
| `apply_setup_areas` | Apply areas and settings from the installer (reads stdin) |
| `reconcile_selfhost_domains` | Promote self-host custom domains to Verified |
| `recompute_storage` | Recompute per-space storage usage |
| `seed_demo`, `seed_showcase`, `seed_e2e` | Demo and test data. Refused on production databases |

### Accounts and sign-in

| Command | Purpose |
| --- | --- |
| `reset_mfa <username> --reason "..."` | Reset one person's two-step sign-in |
| `staff_mfa_readiness` | List elevated accounts with no second factor |
| `recover_superadmin <username>` | Recover a superadmin (`--reset-mfa`, `--password`) |
| `set_login_methods` | Change install-time MFA and built-in provider choices (`--mfa on\|off`, `--providers google,apple,github`) |
| `configure_social_auth` | Set Google client IDs |
| `login_security` | `--list`, `--allow <cidr>`, `--unblock <ip\|all>` platform IP access |
| `account_unification_report` | Report on account unification |

### Backups, keys and recovery

| Command | Purpose |
| --- | --- |
| `backup_preflight`, `backup_control` | Host-side coordination for restore |
| `backup_keys status\|rotate\|reencrypt\|purge` | Backup key rotation and re-encryption |
| `fetch_offsite_archive` | Fetch and verify an archive from an offsite destination |
| `extract_space_restore_point` | Extract one space from a whole-platform archive |
| `import_backup_archive`, `preflight_backup_import` | Import and check an archive |
| `export_portable_tenant_dump`, `import_portable_tenant_dump`, `export_tenant_migration_archive` | Tenant move tools |
| `recover_source_migration_gate` | Reopen an expired or orphaned source migration gate |
| `rls_status`, `rls_sync` | Row-level security mode and policies |
| `verify_storage` | Qualify the configured object storage |

### Encryption and audit

| Command | Purpose |
| --- | --- |
| `backfill_scoped_pii`, `reindex_scoped_pii`, `decrypt_scoped_pii` | Scoped PII encryption maintenance (per space and model) |
| `open_pii_write_fence`, `close_pii_write_fence`, `bind_pii_search_key` | Fence and key binding for that maintenance |
| `redact_platform_email_logs` | Redact stored platform email logs |
| `verify_audit_log`, `verify_audit_macs` | Verify audit integrity |
| `rotate_audit_signing_key` | Rotate an audit signing key (`--dry-run` or `--execute`) |
| `provision_audit_mac_keys` | Provision audit MAC keys |

### Operations and integrations

| Command | Purpose |
| --- | --- |
| `run_scheduled_tasks` | Run periodic tasks with no Celery beat (`--due-only`, `--task`, `--lane`, `--loop`) |
| `flush_email_outbox` | Re-enqueue failed or stalled outbound email |
| `api_client_enforcement_report` | What blocks enforcing API-client auth |
| `openapi_contract_check` | Check every OpenAPI operation documents tags, security, bodies and errors |
| `analytics_sync` | Rebuild the curated analytics views |
| `send_return_reminders` | Send loan return reminders |
| `notification_cutover` | Notification migration tooling |
| `refresh_github_contributions` | Refresh maker-profile contribution counts |
| `provision_native_app_registrations` | Register native mobile apps |

> **Tip** Every command supports `--help`. Commands whose names start with an underscore are internal fixtures and are not part of the supported surface.

## See also

- [Install and update](../install-and-update.md)
- [Backup and restore](../backup-and-restore.md)
- [Upgrade safely](../how-to/upgrade-safely.md)
