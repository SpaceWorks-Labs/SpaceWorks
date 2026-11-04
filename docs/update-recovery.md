# Database recovery after an update

`update.sh` keeps a compressed plain-SQL database dump at
`backups/pre-update-<timestamp>.sql.gz`. An automatic rollback changes application images only.
Forward migrations remain applied; the dump is never restored automatically. Restoring a database
loses database changes made since the dump. The dump contains no uploaded object bytes.

The updater downloads the selected repository's exact release commit archive over HTTPS,
checks the tag's commit suffix, archive paths, release version and complete runtime manifest,
then runs that bundle's updater against the existing installation. It keeps the configured
repository and requested version. Host files are replaced only after the active-database backup;
changed website/API edges and Caddy are recreated so their bind mounts load the new files.
Image rollback also recreates those edges; it retains the new host bundle and forward schema.
Older or conflicting release run numbers are refused, including with `--force`; use the explicit
recovery procedure below when restoring an earlier release.

Before Compose can run migrations, the updater stops **backend, worker, beat and live**.
This is done on every release replacement, so pending data migrations run with local writers stopped.
Operators must also fence external clients, schedulers and other writers; the updater cannot stop
processes outside its Compose installation. If migration fails, image rollback keeps the forward
schema; irreversible conversions still require the reviewed backup/recovery procedure below.

## Fixed-role upgrade (2026-10-16)

The fixed-role data migration (`makerspaces/0092_fixed_roles_data`) is **irreversible**. It replaces
editable roles with seven built-ins and moves Machine Manager type assignments to each person.
Plan this as a stopped-writer upgrade, before invoking any updater that automatically runs migrations.

1. Suspend automatic deployments. Take and verify a database backup, retain the old image/version,
   encryption keys and deployment configuration, and preserve uploaded objects through the normal backup
   procedure. An application-image rollback cannot undo this data conversion.
2. Stop every application writer: web/API, workers, scheduled jobs, live processes and external clients.
   Keep the database available. Use a one-off management process from the **new image**, against the
   still-unmigrated database; do not start its web/worker processes or automatic migration entrypoint.
3. Run `python manage.py preview_fixed_roles` in that new-image management process **before `migrate`**.
   It reads the old schema without writes. `--json` and `--makerspace ID` are available for inspection;
   review an unfiltered preview before upgrading the deployment. Check each membership's mapped role
   set, dropped actions, E1/E2 gains, revoked invitations, pruned schedules and machine reach.
4. Resolve every **“must fix before upgrading”** notification rule. A `NotificationRecipient` with
   `kind=role` referencing an obsolete/custom role makes migration refuse and roll back. Repoint it
   to a surviving built-in or named users, or remove it using the old console. If the console is
   needed, reopen the old image briefly for those controlled edits, then stop all writers again,
   take a fresh backup and rerun the preview. There is no automatic role-to-user conversion.
5. With a clean, reviewed preview and writers still stopped, run `python manage.py migrate` using
   the new image and the installation's normal management/migration authority. Start the new release
   through its existing readiness gates. Verify role sets, notifications and per-person machine types
   in Users/Members before reopening access or resuming scheduled jobs and automatic deployments.

Mapping normally only narrows raw grants. E1 restores the canonical grants of a narrowed Space Manager;
E2 turns the legacy six handout actions into Handover, adding direct job collection. Preview reports
these exceptions. Machine links are dropped, never widened to whole types. A nonempty machine-only
scope loses Machine Manager to avoid widening notification fallback. Former exempt managers mapped
to Machine Manager receive only the types present at migration time; future types need assignment.
Space Manager remains exempt. Reversing the conversion requires a coordinated database restore and
old image, with the data-loss and object-continuity limits described below.

## Inspect a failed deployment

As the install owner, inspect logs before restarting anything:

```bash
bash scripts/spaceworks-compose.sh bundled ps -a
bash scripts/spaceworks-compose.sh bundled logs orchestration-init migrate orchestration-ready backend
```

Use the installation's recorded layer through the wrapper. Failed run-once containers remain for
inspection. A successful application-image rollback
leaves `.spaceworks-version` at the previous immutable release. If the previous release is healthy,
no database restoration is normally needed.

If an installer upgrade stopped while replacing its host runtime bundle or refreshing Compose trust
records, the error names a `backups/host-config-*` directory. Keep application writers stopped; as the
install owner, restore the saved runtime files to their original relative paths, then run
`bash scripts/init-host-orchestration.sh` with the installed version's backend image tag to recreate
matching configuration proofs. Then recreate the configured proxy edges with the wrapper's
`up -d --no-deps --force-recreate`: `frontend` for a website or `api-edge` for API-only, plus `caddy`
for TLS/SaaS layers. Atomic file replacement requires new bind mounts, even when Compose YAML
has not changed. This is host configuration recovery and does not restore the database.

## Moving off a single-box install

The single-box shape and its all-in-one image are no longer available. Before updating, run these
commands from the install directory using the **CURRENTLY INSTALLED scripts**:

```bash
bash scripts/spaceworks-compose.sh bundled stop app
bash scripts/spaceworks-compose.sh bundled rm -f app
printf 'none\n' > .spaceworks-layer
bash scripts/spaceworks-compose.sh bundled up -d
```

Then re-run the update. Data in the database and storage volumes is unchanged.

An older updater on a single-box host takes the database backup and refreshes host topology records,
then fails pulling the no-longer-published all-in-one image before replacing any container. Nothing
was deployed — follow the switch steps above, then retry.

## Restore a pre-update SQL dump

This is an offline database-owner recovery procedure, separate from verified archive restore.
Do not pass a `.sql.gz` file to `scripts/restore.sh`: that supervisor accepts a recorded restore UUID
and a verified archive, not a SQL dump.

1. Suspend automatic deploys by setting the GitHub repository variable `SPACEWORKS_DEPLOY=false`,
   then stop the runner service with `sudo ./svc.sh stop` from its installation directory (default
   `/opt/spaceworks-runner`). Confirm no updater, backup or restore is running. Keep the shared
   host operation lock held through recovery, using Linux/WSL2 `flock`; do not clear a live lock.
2. Save the failed database and current `.env`, host pointer/configuration and version marker before
   replacing anything. Keep the object-storage volumes and continuity encryption keys unchanged.
3. Confirm the database name and server from the **active host database pointer**, and confirm that
   identity is the database captured by the selected dump. H1 recovery can change that pointer:
   `POSTGRES_DB` is not proof of the live application's database. A database owner must review this
   identity before any drop, create or restore command. Managed/external databases need their provider's
   restore procedure and pointer/CAS adapter; the bundled-container procedure does not apply to them.
4. Stop the whole application stack, including web front, live streams, workers and
   schedulers. Keep only the database container running. Confirm all writers are disconnected. Check
   the dump's integrity with `gzip -t backups/pre-update-<timestamp>.sql.gz`.
5. As the database owner, recreate the explicitly confirmed target database and stream the decompressed
   SQL into `psql` with `ON_ERROR_STOP=1`. Use the matching client inside the database container. Do not
   import into a database still holding application tables, and do not ignore SQL errors. A partial
   import stays offline until a complete restore succeeds.
6. Reprovision the least-privilege runtime grants for that exact database through the shipped
   orchestration-ready grants-only path (`SPACEWORKS_GRANTS_ONLY=1` and
   `SPACEWORKS_GRANT_DATABASE_NAME=<confirmed database>`). Verify the active pointer still names it.
7. Set the previous immutable release's image tag and `.spaceworks-version`, pull those application
   images, and start through the existing orchestration/migration gates. Check readiness before
   reopening access or restarting the deploy trigger. If grants, host trust, recovery gates or
   readiness refuse startup, keep writers stopped and resolve the refusal.

A SQL-only restore does not reproduce object bytes or rewind object mutations after the dump. For
coordinated database/object recovery use a compatible verified deployment archive and its recovery
workflow. Do not waive the host capability, signature, compatibility or quarantine gates.

## Existing verified archive restore

The backup feature and its independent host supervisor remain. Request/confirm the restore through
its existing backup workflow and obtain the recorded RestoreOperation UUID. For an admitted legacy
in-place restore, run on Linux/WSL2 with the configured age identity and required host privileges:

```bash
sudo bash scripts/restore.sh <restore-uuid>
```

The supervisor verifies the archive and compatibility before destructive changes, drains writers,
takes its own pre-restore snapshot, restores the database and objects, reprovisions grants, and checks
readiness/recovery state. Follow any restore-diff decision in the backup console. A disaster/reset
restore enters quarantine: run the existing superadmin recovery workflow and acknowledge residual risk
before allowing normal writes. Interrupted destructive work uses its durable rollback journal.

Before any control-state change, snapshot, restore or interrupted rollback, `restore.sh` queries
the active application's database name, OID and deployment UUID through the committed wrapper,
and compares them with a direct query of the bundled bootstrap database while holding the host
operation lock. The complete identities must match. A sibling cutover or external database pointer
is refused **before any restore effect**; use the supported cutover recovery coordinator instead.
Every snapshot, replacement, rollback and grant reprovisioning uses that explicitly proven database
name. Do not reset the pointer to make the check pass.

`restore.sh` is the legacy path and refuses compound envelopes, including envelopes without sovereign
slices. Compound archives require their supported host coordinator;
do not force them through the legacy supervisor or treat a verified offsite copy as a proven restore.
