# SpaceWorks operator manual

This guide is for the person who runs a SpaceWorks deployment. A Space Manager handles routine work inside one space. A platform superadmin handles platform settings, recovery and space lifecycle actions.

## Install and check the deployment

1. Choose your hosting shape. The full VPS installer is the default self-hosting path. For split hosting, choose where the API, browser frontend and object storage will run before configuring origins. [Choose your hosting](choose-your-hosting.md)
2. Install a published version and keep a record of the version, domain and recovery key custody. Use the guided installer or the recipe for your deployment shape. [Install and update](install-and-update.md) · [Self-hosting](self-hosting.md)
3. Check the health endpoints, migrations, background jobs and storage before inviting users. Verify browser login and an evidence upload from the real frontend origin. [Health checks](self-hosting.md#health-checks) · [Object storage](self-hosting.md#object-storage)

Use the web superadmin console for day-to-day platform operations. The Django control plane is server-only by default. Use the documented local or SSH tunnel access for host-only operations. [Reach the control plane](self-hosting.md#reaching-the-control-plane)

## Update or recover

1. Choose the target release and review its deployment notes. Confirm you can access a current recovery artifact before updating.
2. Run the update using the instructions for your hosting shape. Check application health, background jobs and staff sign-in after it finishes. [Updating](install-and-update.md#updating)
3. If the database recovery gate activates, follow the database recovery guide for the verified artifact and target version. Keep the prior artifact until the deployment and its data are verified. [Database recovery](update-recovery.md)

## Back up, restore and rotate keys

- Use whole-deployment backups for server recovery. Keep the platform archive identity off the server. Use one-space restore points for a space restore. [Backups](self-hosting.md#backups)
- Preview a one-space restore, then confirm the password and space slug. The restore flow takes a safety backup before changing the space. [Restore one space](self-hosting.md#restore-one-space)
- Check recent restore drill results. A drill uses a throwaway database and key. Follow up on a failure before relying on the affected archive. [Restore drills](self-hosting.md#restore-drills)
- When rotating an archive key, retain the previous identity until archives that still depend on it have been re-encrypted, retained under documented custody, or deliberately purged. [Rotate a backup key](self-hosting.md#rotate-a-backup-key)
- Use the approved tenant transfer workflow for a move from another deployment. Verify the encrypted artifact digest and use the destination's import identity. Complete identity conflict decisions before activation. [Move a space to this server](self-hosting.md#move-a-space-to-this-server-self-host-move)

## Modules and data

- A Space Manager switches modules and features on or off for their own space. Switching off hides the surfaces and keeps the data; see the [switch-off reference](MODULES-OFF.md) for what each of the 37 modules and 209 features keeps.
- Two things stay with the platform: installing a module that carries a usage limit on a managed platform (self-hosted installs have no such limit), and every purge. [Module lifecycle](MODULES-LIFECYCLE.md) · [Choosing modules](choosing-modules.md)
- Purge a switched-off feature's maintenance, To-Buy or warranty data from the space's control-plane page with **Preview and purge switched-off maintenance, To-Buy or warranty data**. Purge a whole module's data from the server with `python manage.py purge_module_data`; list modules first with `list_modules`. A purge cannot be undone. Payment records are always kept and each purge is audited. [Deleting a module's data](MODULES.md#deleting-a-modules-data)
- `machines.integrations` is the one feature with no staff-console switch; turn it on in the control plane only.

## Monitor and investigate

- Check `GET /api/v1/health/` (alive) and `GET /api/v1/health/readiness/` (ready) after every update or restore. The superadmin **Platform dashboard** runs the deeper checks every 15 minutes: backups, off-site copies, scheduler, updates, email, storage and domain. [Platform monitoring](platform-monitoring.md) · [Monitoring and analytics](monitoring-and-analytics.md)
- Trace a failed request with its `X-Request-ID` through the API and worker logs, and read recorded actions in the audit log. [Logging and audit](logging-and-audit.md) · [Audit action reference](audit-action-reference.md)

## Operate a space

In the web superadmin console, open **Platform → Spaces** and choose the space.

| Task | Control | Effect |
| --- | --- | --- |
| Temporarily stop service | **Suspend** | Public, member and ordinary staff service pauses. Existing data stays. |
| Let people read while blocking changes | **Make read-only** | Members and ordinary staff keep their permitted read access. Superadmin bypasses are audited. |
| Give someone else ownership | **Transfer ownership** | An existing member can become manager. A new person receives an invitation. |
| Close a space | **Schedule archive & purge** | Confirm the exact slug and review the archive date and grace period. Export anything needed before the permanent purge. |
| Inspect a space | **Health** | Review service state, usage, backup and drill results, and open issues. |

See the [space lifecycle guide](self-hosting.md#operating-your-spaces-superadmin-controls) for scheduling and reversals. Use the [own-domain guide](own-domain-and-frontend.md) for a Space Manager's DNS verification flow. Keep operator actions traceable through [logging and audit](logging-and-audit.md).
