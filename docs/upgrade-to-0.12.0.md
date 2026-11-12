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
- **Certifications are gone.** Migration `machines.0040` converts them to machine access grants and opens ungated machines to all members; read [Give members machine access](how-to/machine-access.md#what-happened-to-certifications-on-upgrade) and check the machines you expect to stay restricted afterwards. The old certification routes answer `410`.
- **Profiles and usernames.** Per-space profiles are merged into one account profile (`makerspaces.0152`, `0153`) and older accounts are asked to choose a username on next sign-in. Before that, `scripts/update.sh` runs `python manage.py claim_default_handles` once (marker file `.spaceworks-handles-claimed-0.12.0`): every existing account whose username is a valid, free handle gets it, so most people never see the step. It is idempotent and only warns on failure. Cloud, Helm and managed deployments run it once after the migrate step, like `recompute_storage`. See [the profile guide](how-to/member-profile.md).
- **Printing is part of Machine service.** The separate `printing` module ("a 3D print queue") is retired: Machine service handles service requests for every machine type, and the 3D print queue is one machine type inside it. Migration `makerspaces.0154_retire_printing_module` keeps Machine service on for every space that had printing on, removes the stored `printing` key and writes one `makerspace.module_retired` audit row per space; it is reversible. A space with Machine service on but printing off now also offers the public print form, print tracker and filament-pool choice, so check the 3D printer queues you publish. The `print` limit, the printer service report, print notifications and the `printing_requests` workflow all moved to Machine service. Anything that still says `printing` (an older backup or tenant dump, a hosting plan, an API client, `install_module printing`) is read as `machine_service`; `uninstall_module printing` is refused (uninstall `machine_service` instead) and `update.sh --without=printing` changes nothing. `/features/printing` redirects to `/features/machine-service`.
- **Public print form.** A space with Machine service on (including every space that had printing on) offers the public 3D print form, print tracker and filament-pool choice. Check which printer queues you want published before reopening.
- **Consumable profiles.** `machines.0041` to `0043` create per-machine-type consumable profiles from each space's existing consumables, without changing any price, and add per-type booking defaults, training notes and documents. Review each machine type under **Machines, Types** after the update ([guide](how-to/machine-consumables.md)).
- **Machine use for an event** has no switch; it is always available on sessions and service requests ([guide](how-to/machine-use-for-events.md)).
- **Anthias players and private addresses.** A player on a private network address is allowed by default on a self-hosted install and refused by default when `SPACEWORKS_DEPLOYMENT_MODE=managed`. Set `ANTHIAS_ALLOW_PRIVATE_HOSTS` to change either. The server's own service networks and cloud metadata addresses are always refused; add more ranges with `OUTBOUND_BLOCKED_NETWORKS`. Changing a player's address now clears its stored password. Webhook, Anthias and image-adapter calls are pinned to the address that was checked.
- **Display screens.** A screen sends its secret in an `Authorization: Display <secret>` header to `/api/v1/space-displays/state/`. The old path-secret route still answers, is marked deprecated and is blanked out of access logs; it will be removed later. If you cannot trust past access logs, press **New address** on link screens or unpair and pair code screens ([guide](how-to/display-screens.md#if-your-server-logs-are-older-than-release-0120)).
- **Rate limits.** Every route without its own limit now has a deployment-wide ceiling (`THROTTLE_DEPLOYMENT_ANON` 600/min per client, `THROTTLE_DEPLOYMENT_USER` 1200/min per account, `THROTTLE_DEPLOYMENT_DEVICE` 600/min per device). Profile lookups, username checks, display claims, Anthias tests, adapter calls and camera watch have their own scopes; see [new environment variables](#new-environment-variables). A busy integration or a kiosk fleet behind one address may need a higher value; a platform operator can also override a rate in the console. Behind a reverse proxy, set `TRUSTED_PROXY_COUNT` correctly so limits key on the real client address.
- **Redis.** Bundled Redis stays the default (external Redis and the opt-in "no Redis, cron mode" choice are unchanged). The bundled image is pinned (`REDIS_IMAGE_TAG`, default `7.4.11-alpine`, was an unpinned `redis:7-alpine`), runs with append-only persistence on a new `redis_data` volume and has a memory cap (`REDIS_MAXMEMORY`, default `512mb`, `volatile-lru`). On upgrade that volume starts empty, so jobs still queued in Redis at that moment are not carried over; the updater stops services first, so queues are normally empty. If Redis is unreachable the API stays up (rate limits fall back to per-process counters) while single-use security checks answer 503 with `Retry-After`. `rediss://` now verifies certificates. See [Redis](architecture/redis.md).
- **Card photos and the background eraser.** `card_designs.0013` stores the eraser notice version and members' opt-outs. Members who opt out are never sent to the removal service. Member-card photos are accepted up to 8 MB (a larger file is refused before upload) and are re-encoded with location data removed. Where the eraser can run, the public privacy page shows the notice.
- **Adapter PIN for `card_qr`.** An adapter credential check with a member card QR now also needs the member's PIN (`pin_required` otherwise), and a public card verification link is never accepted as a credential. All member-level failures answer the same `unknown_credential`, and each device and space has a budget of failed attempts per 15 minutes. Update any adapter that sent a card QR alone.
- **Adapter logs are append-only in the database** (`devices.0013`), and adapter-reported session minutes are capped at the session's real elapsed time, with outliers flagged for staff.
- **Machine access grants belong to one space.** A grant's machine type is resolved per space and the built-in types can be granted; the upgrade conversion handles both.
- **Profiles.** Minors' profiles are visible only within their own spaces, platform-wide profile reads and username checks are throttled, and a handle release cooldown only blocks changing the handle. The member data export now includes the profile.
- **Eraser, certificates and templates.** `CERTIFICATE_SHARED_RENDERER` stays off by default and is pinned per certificate.
- **Sign-in guards.** Removing the last passkey, phone or social sign-in is refused; a linked identity provider's slug and issuer are locked. See [Sign-in methods](guide/sign-in-methods.md).
- **Native apps** are distributed through GitHub Releases only.
- **Front page.** `HUB_LANDING_ENABLED` defaults to on. A space that wants its own home at `/` sets it to `False` (`bash scripts/apply-settings.sh --landing off`).
- **Device adapters, the background eraser and bulk photo upload** are off until their switches are on. If you put your own reverse proxy in front, allow 25 MB (or 220 MB for a zip) on the bulk photo route; see [Remove card photo backgrounds](how-to/background-eraser.md).
- No new operator setting is required. Optional device-adapter settings are in the [environment reference](environment-reference-delivery.md#device-adapters).

## New migrations

New relative to the 0.11.0 candidate tree (the state at the 0.11.0 notes commit); `python manage.py showmigrations` lists them in order:

| App | Migrations | Notes |
| --- | --- | --- |
| `accounts` | `0058` to `0060` (3 migrations, from `0058_oidc_attempt_next_path`) | OIDC next path, staff invitation machine ids, the requested username on an email challenge. |
| `analytics` | `0002` to `0003` (2 migrations, from `0002_telemetry_config`) | Web telemetry configuration; Grafana connection. |
| `audit` | `0011_venue_fee_payment_index` | **0011 is non-atomic** (`CREATE INDEX CONCURRENTLY`); existing audit rows are not rewritten. |
| `bookings` | `0024` to `0031` (8 migrations, from `0024_loan_context`) | Loan and consumable-plan context, booking replacement, included hours, house bookings, organization link, three-decimal money, organization hours bank. |
| `boxes` | `0013_qrcode_external_source` | External QR source. |
| `card_designs` | `0004` to `0013` (10 migrations, from `0004_card_design_archived_at`) | Archived designs, Outfit font family, wallet credentials, event badge roles, staff cards, background eraser results, saved templates, eraser notice version and member opt-outs. |
| `devices` | `0006` to `0013` (8 migrations, from `0006_device_adapter_api`) | Device Adapter API: models, jobs, kiosk, media, artifacts and offline data; telemetry and detection tables; shelf checks (`0012`); database triggers that make adapter logs append-only (`0013`). |
| `event_reimbursements` | `0009` to `0010` (2 migrations, from `0009_staff_claims`) | Staff claims; required stage ceiling. |
| `events` | `0085` to `0101` (17 migrations, from `0085_loan_context`) | Loan context, event-booking decision and its guard, machine booking link, equipment, staff invite limits, crew and teams, series and check-in lists, search, external venue, card roles and badge prints, machine use linked to an event (`0100`, `0101`). |
| `hosting_requests` | `0004_requested_kind` | Requested kind. |
| `id_programmes` | `0003_programme_archived_at` | Archived programmes. |
| `integrations` | `0052` to `0055` (4 migrations, from `0052_firebase_web_config`) | Firebase web config, platform credential switch, webhook secret, platform legal pages. |
| `inventory` | `0018` to `0022` (5 migrations, from `0018_equipment_proposals`) | Kits and proposals, snapshot guards, consumable use receipts, event-only products, three-decimal money. |
| `machines` | `0034` to `0043` (10 migrations, from `0034_builtin_cnc_router_name`) | 0034 restores the built-in "CNC Router" name only where it was left as "Cnc Router"; 0036-0038 supervised sessions and membership machine scope; 0039-0040 machine access grants (0040 is a data step that converts certifications and is not undone by an image rollback); 0041-0042 consumable profiles and their seed from existing consumables (`0042` is a data step); 0043 per-type booking defaults, training notes and documents. |
| `maintenance` | `0007` to `0012` (6 migrations, from `0007_issue_report_return_line`) | Repair issue from a return line, machine sessions, incident register, three-decimal money. |
| `makerspaces` | `0134` to `0154` (21 migrations, from `0134_loan_context_generations`) | Loan-context generations, guest passes, minors and volunteers, Fundraising role, member units, space kind, email sender verification, the global account profile (0152) and the merge of per-space profiles (0153). |
| `managed_hosting` | `0002` to `0006` (5 migrations, from `0002_hosting_switch`) | Hosting switch, throttle rate, hosting type, platform default limits (`0006`). |
| `notifications` | `0012_browser_firebase_registration` | Browser Firebase registrations. |
| `organizations` | `0009_review_status` | Review status. |
| `payments` | `0046` to `0051` (6 migrations, from `0046_guest_pass_subject`) | Guest pass subject, donations, loan labels, three-decimal money, financial-year receipt series. |
| `presence` | `0004` to `0006` (3 migrations, from `0004_display_screen`) | Display screens, account-level presence, display panel settings and Anthias players (`0006`). |
| `procurement` | `0011_money_three_decimals` | Three-decimal money. |
| `shop` | `0003` to `0006` (4 migrations, from `0003_shop_event_offer`) | Event offers, three-decimal money, order idempotency key. |

`makerspaces.0152`, `machines.0039` and `machines.0040` were revised during the release work. A database that applied an earlier source build of this branch should be restored from backup or rebuilt rather than moved forward over those migrations.

`machines/0017_seed_machine_type_metering_packs` was also edited so that a fresh database keeps the built-in names; databases that already applied it are corrected by `0034`.

Installations coming from 0.9.2 or 0.9.3 additionally apply every migration added in the 0.11.0 candidate (for example `hardware_requests` `0030` and `0031`).

Because `audit.0011` is non-atomic, an interrupted run can leave an invalid `audit_venue_fee_payment_idx`. Before retrying, check `pg_index.indisvalid` for that index and, if it is invalid, drop it with `DROP INDEX CONCURRENTLY` and rerun the migrations. Several new migrations add database guards or data steps with no-op reverses, so they are not reversed by an application-image rollback.

## New environment variables

None is required. All are optional and have working defaults; the full list with descriptions is in the [environment reference](environment-reference.md). New since the 0.11.0 candidate:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HUB_LANDING_ENABLED` | on | The scrolling product page at `/`. |
| `THROTTLE_DEPLOYMENT_ANON` / `_USER` / `_DEVICE` | 600/min, 1200/min, 600/min | Deployment-wide rate ceilings. |
| `THROTTLE_PROFILE_LOOKUP`, `THROTTLE_PROFILE_LOOKUP_DAILY` | 30/min, 500/day | Signed-in profile reads. |
| `THROTTLE_HANDLE_CHECK`, `THROTTLE_HANDLE_CHECK_DAILY` | 20/min, 300/day | Username availability checks. |
| `THROTTLE_MINOR_PERSON_LOOKUP` | 60/min | Staff person lookup for minors and guardians. |
| `THROTTLE_ANTHIAS_PLAYER_CALL`, `THROTTLE_IMAGE_ADAPTER_TEST` | 20/min, 10/min | Anthias and image-adapter test calls. |
| `THROTTLE_DEVICE_ADAPTER`, `THROTTLE_DEVICE_ADAPTER_CREDENTIAL` | 300/min, 60/min | Signed adapter calls and credential checks. |
| `THROTTLE_ADAPTER_WATCH_START`, `THROTTLE_ADAPTER_WATCH_RELAY` | 10/min, 300/min | Camera watch. |
| `ANTHIAS_ALLOW_PRIVATE_HOSTS` | on (self-host), off (managed) | Anthias players on private addresses. |
| `GRAFANA_ALLOW_PRIVATE_HOSTS` | off | Grafana on a private address. |
| `OUTBOUND_BLOCKED_NETWORKS` | empty | Extra ranges tenant-configured outbound calls may never reach. |
| `ADAPTER_ACCESS_CACHE_TTL_SECONDS`, `ADAPTER_ARTIFACT_RETENTION_DAYS`, `ADAPTER_CACHE_KEY_*`, `ADAPTER_TELEMETRY_*`, `ADAPTER_TURN_*` | see reference | Device adapter caches, retention, telemetry rollups and TURN. |
| `CERTIFICATE_SHARED_RENDERER` | off | Event certificates on the shared card engine. |
| `ORGANIZATION_PUBLIC_DIRECTORY_ENABLED`, `ORGANIZATION_REVIEW_REQUIRED` | see reference | Organization directory and review. |
| `PUBLIC_SPACE_REQUESTS_ENABLED` | off | Public request form for a space or organization workspace on a self-hosted install. |
| `WEB_TELEMETRY_ALLOWED_ORIGINS` | empty | Origins a self-hosted page-analytics provider may use. |
| `REDIS_IMAGE_TAG`, `REDIS_MAXMEMORY` | `7.4.11-alpine`, `512mb` | Bundled Redis (host settings in `.env`). |

Operators coming from 0.9.2 or 0.9.3 also have every variable added for the 0.11.0 candidate (see its upgrade guide).

## Upgrade steps in order

1. Back up the database and object storage and record the installed tag (see above).
2. Run `scripts/update.sh --version <tag>` (or the installer's update choice). It stops services, starts the pinned Redis with its new empty volume, migrates and starts the application.
3. The updater runs `recompute_storage` and `claim_default_handles` once each (marker files in the install directory). On cloud, Helm and managed deployments run both once after the migrate step.
4. If you run your own reverse proxy, allow 25 MB (220 MB for a zip) on the bulk card photo route, set `TRUSTED_PROXY_COUNT` to the number of proxies, and check the new rate limits against your integrations.
5. Review machine types, Anthias players and published printer queues as described above, then work through the checks below.

## Verify before reopening

1. Check health/readiness, applied migrations (including a valid `audit_venue_fee_payment_idx`) and strict row-security status under the runtime login. Verify that the runtime role is neither superuser nor BYPASSRLS and owns no scoped tables.
2. Sign in as a member and staff actor with the configured second factor. Check the makerspace overview, separate Inventory and enabled module navigation.
3. Exercise an evidence upload and a complete authorized loan issue/return, with and without an event or booking context. Confirm stock and audit history. Check a staff booking with price confirmation and the areas used by the installation.
4. Inspect background workers or the selected free/brokerless scheduler, object storage and the configured local/provider email path. Check retained balances and offline receipts before enabling online payment credentials.
5. Check related facts, event linked finance and the loan-context reports with an authorized and an unauthorized staff actor.
6. Check a display screen and, if used, an Anthias player; the Redis container (`redis-cli ping` inside it) and that `redis_data` is mounted; one machine type's consumables. Check existing Shop orders, a QR revocation and its audit record, and any printed output used by the installation.

If an update fails, preserve logs and the previous artifact. An application-image rollback does not undo forward database migrations. Use the [database recovery procedure](update-recovery.md) for the verified backup and matching object state. Upgrades are **forward-only by policy**: the updater refuses to deploy a release older than the one installed, so the only way back to 0.9.2 is restoring the verified pre-update backup ([Rolling back](install-and-update.md#rolling-back)). The automatic rollback after a *failed* update only restarts the images that were running when it began.

Release status: the complete backend/runtime regression, browser suite, PostgreSQL scenarios for the new connections, deployment and old-version upgrade acceptance are still pending. Do not read this procedure as a record that those checks have already passed.
