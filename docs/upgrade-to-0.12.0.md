# Upgrade to SpaceWorks 0.12.0

This guide covers updating to 0.12.0 from a published 0.9.2 or 0.9.3 installation, and from a local build of the unpublished 0.11.0 candidate. There is no published 0.10 or 0.11 release. Use the published immutable 0.12.0 release tag once it exists; a dev branch or an unpublished candidate is not an installable release identifier.

## Before updating

1. Record the installed immutable tag, image digests and hosting topology. Pause the automatic deploy runner and other writers or schedulers for the maintenance window. Keep the previous images available.
2. Verify a current database and object-storage backup, deployment configuration, active database identity and encryption-key custody. The updater's pre-update SQL dump does not include uploaded objects. See [backups](self-hosting.md#backups) and [database recovery](update-recovery.md).
3. If the installation still uses the retired all-in-one image, follow [moving off a single-box install](update-recovery.md#moving-off-a-single-box-install) before the update. Published deployments use the standard `spaceworks-backend` and `spaceworks-frontend` images.
4. Coming from 0.9.2 or 0.9.3: if the database predates the fixed-role conversion, complete the [fixed-role preview and stopped-writer upgrade](update-recovery.md#fixed-role-upgrade-2026-10-16). Review obsolete notification recipient roles and Machine Manager type assignments. Account/role conversions marked irreversible require a verified backup first.
5. Allow time for the `audit` concurrent index build on a large audit log (see [new migrations](#new-migrations)).

## Apply the published release

Use **Update to the latest release** in the installer, or run the installed updater with the exact published immutable suffix:

```bash
bash scripts/update.sh --version 0.12.0-main.<run>.<sha>
```

Replace the placeholders with the actual published tag. Keep the documented cloud or Helm procedure for that deployment shape. The standard wrapper preserves fork overrides while migrating the upstream repository and default images from SpaceWorks-HQ to SpaceWorks-Labs.

The updater backs up the active database, stops local application writers, runs migrations and checks readiness before reopening. Inspect failed run-once services before retrying. Do not treat a backend restart or a source build as a verified published-image update.

## From 0.9.2 or 0.9.3

Every change prepared for the 0.11.0 candidate arrives in this update. Read [Upgrade to the 0.11.0 candidate](upgrade-to-0.11.0.md#review-changed-behavior-and-settings) for the changed behaviour and settings: the separate Inventory page, light mode default, public-stat settings, account-owned histories, Shop return window, independent credential switches, QR revocation, asset-unit generation, card templates, the retired Check-In integration, backup compatibility seams and the server-only control plane. Then review the 0.12.0 changes below.

## From a 0.11.0 candidate build

A candidate build was never a published tag, so the updater cannot select it as the installed release. Treat it as a source build: back up, then update to the published 0.12.0 tag. Only the migrations listed below are new relative to the candidate tree.

## Review changed behavior and settings

- Loans can carry an event and/or booking context, and staff can manage published equipment kits. Existing loans stay ordinary (no context) until staff add one. See [equipment loan context](equipment-contexts.md) and [equipment kits](equipment-kits.md).
- An event linked to a room booking has no event venue fee: the booking owns the single room charge. Linking is refused while an event venue fee is configured or has payment history, so review such events before linking.
- The staff console previews the booking price and sends its `price_confirmation` on single-booking create; a stale confirmation is refused with `price_changed` before anything is written. The field is optional on the single-booking create API, so existing integrations keep working; a booking replacement always goes through a staff price confirmation.
- Queue estimates now apply the maintenance lockout rule. Machines with overdue blocking maintenance stop appearing available in the queue.
- Revoking a person's authentication also ends their personal access tokens and disconnects their OAuth app connections. Revoked API integrations must be reconnected.
- Direct-room notification delivery fails closed when its lookup errors: that room delivery is not sent, while independent email delivery stays eligible.
- Storage usage is recomputed once. After the new release is healthy, `scripts/update.sh` runs `python manage.py recompute_storage` in the backend container for every existing makerspace, so displayed usage and storage limits start from the true figure. It is idempotent, leaves a space unchanged when storage cannot be read, only warns on failure, and is skipped on later updates by the marker file `.spaceworks-storage-recomputed-0.12.0` in the install directory. Cloud, Helm and managed deployments, which do not use `update.sh`, run `python manage.py recompute_storage` once in the backend container after the migrate step.
- No new operator setting is required for these changes.

## New migrations

New relative to the 0.11.0 candidate tree:

| App | Migrations | Notes |
| --- | --- | --- |
| `analytics` | `0002_telemetry_config` | Adds web telemetry configuration fields. |
| `audit` | `0011_venue_fee_payment_index` | **Non-atomic.** Builds `audit_venue_fee_payment_idx` with `CREATE INDEX CONCURRENTLY`; existing audit rows are not rewritten. |
| `bookings` | `0024_loan_context`, `0025_consumable_plan_context`, `0026_booking_replaces` | Loan and consumable-plan context; one-to-one booking replacement. |
| `events` | `0085_loan_context`, `0086_consumable_plan_context`, `0087_event_booking_decision`, `0088_event_booking_decision_guard` | Event loan context and the immutable event–booking decision with its database guard. |
| `integrations` | `0052_firebase_web_config` | Adds the platform Firebase web configuration field. |
| `inventory` | `0018_equipment_proposals`, `0019_equipment_snapshot_guards`, `0020_equipment_use_receipt` | Kits and proposals, snapshot guards and consumable use receipts. |
| `machines` | `0034_builtin_cnc_router_name`, `0035_consumable_cost_shop_sources` | 0034 restores the built-in "CNC Router" name only where it was left as the generated "Cnc Router". |
| `maintenance` | `0007_issue_report_return_line` | Links a repair issue to a damaged return line. |
| `makerspaces` | `0134_loan_context_generations` | Seeds loan-context generations for every makerspace. |
| `notifications` | `0012_browser_firebase_registration` | Browser Firebase installation registrations. |

`machines/0017_seed_machine_type_metering_packs` was also edited so that a fresh database keeps the built-in names; databases that already applied it are corrected by `0034`.

Installations coming from 0.9.2 or 0.9.3 additionally apply every migration added in the 0.11.0 candidate (for example `hardware_requests` `0030` and `0031`).

Because `audit.0011` is non-atomic, an interrupted run can leave an invalid `audit_venue_fee_payment_idx`. Before retrying, check `pg_index.indisvalid` for that index and, if it is invalid, drop it with `DROP INDEX CONCURRENTLY` and rerun the migrations. Several new migrations add database guards or data steps with no-op reverses, so they are not reversed by an application-image rollback.

## Verify before reopening

1. Check health/readiness, applied migrations (including a valid `audit_venue_fee_payment_idx`) and strict row-security status under the runtime login. Verify that the runtime role is neither superuser nor BYPASSRLS and owns no scoped tables.
2. Sign in as a member and staff actor with the configured second factor. Check the makerspace overview, separate Inventory and enabled module navigation.
3. Exercise an evidence upload and a complete authorized loan issue/return, with and without an event or booking context. Confirm stock and audit history. Check a staff booking with price confirmation and the areas used by the installation.
4. Inspect background workers or the selected free/brokerless scheduler, object storage and the configured local/provider email path. Check retained balances and offline receipts before enabling online payment credentials.
5. Check related facts, event linked finance and the loan-context reports with an authorized and an unauthorized staff actor.
6. Check existing Shop orders, a QR revocation and its audit record, and any printed output used by the installation.

If an update fails, preserve logs and the previous artifact. An application-image rollback does not undo forward database migrations. Use the [database recovery procedure](update-recovery.md) for the verified backup and matching object state. Upgrades are **forward-only by policy (decision 219g)**: the updater refuses to deploy a release older than the one installed, so the only way back to 0.9.2 is restoring the verified pre-update backup ([Rolling back](install-and-update.md#rolling-back)). The automatic rollback after a *failed* update only restarts the images that were running when it began.

Release status: the complete backend/runtime regression, browser suite, PostgreSQL scenarios for the new connections, deployment and old-version upgrade acceptance are still pending. Do not read this procedure as a record that those checks have already passed.
