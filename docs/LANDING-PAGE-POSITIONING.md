# SpaceWorks landing-page modules and positioning

Companion to the [feature inventory](LANDING-PAGE-FEATURES.md).

## Optional modules: landing-page comparison source

This table lists the **30 optional modules** in the current registry: member accounts is on by
default, and the other 29 are opt-in. The six core inventory/workflow/QR/evidence/staff keys remain
available. Maintenance, warranty, repairs and To-Buy are capabilities under their parent areas;
printing is part of machine service. They are not separate installable modules.

| Module key / area | What it adds | Free / paid |
| --- | --- | --- |
| `guest_handover` / Guest handover | Front-desk issue and return of accepted requests. | Works free; no member fee. Online payments optional. |
| `telegram` / Telegram | Per-makerspace Telegram group alerts (outbound only). | Works free; no member fee. External providers can charge the operator; online payments optional. |
| `bulk_import` / Bulk import | Spreadsheet import of inventory rows. | Works free; no member fee. Online payments optional. |
| `containers` / Containers | Physical container hierarchy and moves. | Works free; no member fee. Online payments optional. |
| `stock_transfers` / Stock transfers | Intra- and cross-makerspace stock movement. | Works free; no member fee. Online payments optional. |
| `stocktake` / Stocktake | Scan-first stocktake sessions and variance. | Works free; no member fee. Online payments optional. |
| `reports` / Reports | Analytics, report registry and CSV/XLSX exports. | Works free; no member fee. Online payments optional. |
| `qr_print_batches` / QR print batches | Batched QR label ZIP generation. | Works free; no member fee. Online payments optional. |
| `asset_units` / Asset units | Individually QR-tracked asset units. | Works free; no member fee. Online payments optional. |
| `machines` / Machines | Machine registry, operators, usage and documents. | Works free; optional jobs/material/session fees: `charges.machines`. Online payments optional. |
| `machine_service` / Machine service | Service requests for every machine type (3D printers, lasers, CNC, cutters) and their consoles. | Works free; optional jobs/material/session fees: `charges.machines`. Online payments optional. |
| `events` / Events | Event scheduling and registrations. | Works free; optional tickets/teams/entry/deposits/venue fees: `charges.events`. Online payments optional. |
| `event_reimbursements` / Event reimbursements | Optional event support requests, finite budgets, awards and expense claims. | Works free; no member fee. Online payments optional. |
| `bookings` / Bookings | Resource booking and public self-booking. | Works free; optional resource/time fees: `charges.bookings`. Online payments optional. |
| `membership` / Membership | Join requests, referrals, verification, profiles, directory and member activity. | Works free; optional dues/admission/guest passes: `charges.membership`. Online payments optional. |
| `notifications` / Notifications | In-app notification inbox and emitters. | Works free; no member fee. Online payments optional. |
| `email` / Email | Outbound email delivery for this makerspace. | Works free; no member fee. External providers can charge the operator; online payments optional. |
| `sms` / SMS | Consented member and staff SMS notifications; OTP is independent. | Works free; no member fee. External providers can charge the operator; online payments optional. |
| `whatsapp` / WhatsApp | Consented member and staff approved-template WhatsApp notifications. | Works free; no member fee. External providers can charge the operator; online payments optional. |
| `slack` / Slack | Per-makerspace Slack incoming-webhook alerts. | Works free; no member fee. External providers can charge the operator; online payments optional. |
| `mattermost` / Mattermost | Per-makerspace Mattermost incoming-webhook alerts. | Works free; no member fee. External providers can charge the operator; online payments optional. |
| `discord` / Discord | Per-makerspace Discord incoming-webhook alerts. | Works free; no member fee. External providers can charge the operator; online payments optional. |
| `webhook` / Signed webhooks | Per-makerspace signed JSON webhooks to your own systems. | Works free; no member fee. External providers can charge the operator; online payments optional. |
| `payments` / Payments | Online card payment (Stripe/Razorpay). Money owed is tracked without it. | Works free; adds only the optional online rail. Debt and offline receipts remain core. |
| `member_accounts` / Member accounts | Member self-service enrolment and built-in password, social and phone login. Staff sign-in, external identity and member-domain APIs are unaffected. | Works free; no member fee. Online payments optional. |
| `mobile` / Mobile apps | Attested device sessions, native push and the in-app payment sheet. | Works free; no member fee. External providers can charge the operator; online payments optional. |
| `devices` / Connected devices | Enrolled printers and label printers that authenticate with an Ed25519 key. | Works free; no member fee. Online payments optional. |
| `presence` / Presence | Time-limited member and guest check-in, with a privacy-controlled current-presence display. | Works free; no member fee. Online payments optional. |
| `shop` / Shop | A per-space shop: catalogue, stock, front-desk sales and online orders for pickup, every sale in the finance ledger. | Catalogue and stock work free; selling requires `charges.shop` and `charges.enabled`. Offline cash with a receipt works; online payments optional. |
| `analytics` / Analytics (Metabase, Grafana) | A read-only database login over curated, versioned analytics views and the space's Metabase dashboards embedded in the staff console. | Works free; no member fee. Online payments optional. |

Switching a module off hides its surfaces and keeps its data. Optional links are active only while
both areas are on. The registry requires member accounts for membership and mobile sessions, and
events for event reimbursements; dependency validation controls installation/removal. Turning off the
payments module keeps debts, receipts, reconciliation and member payment history available.

## Customer-controlled feature switches

Modules control whole areas. Settings authority determines who may change an area's narrower
capabilities: the Space Manager, or a specifically delegated area manager where supported.

- `charges.enabled` controls whether any new charge is recorded. Each of `charges.loans`,
  `charges.machines`, `charges.bookings`, `charges.events`, `charges.membership`, `charges.shop` and
  `charges.donations` can be chosen separately. A fully free space switches the master off.
- `payments` is opt-in and adds the online rail alone. Its master/area switches and valid Stripe or
  Razorpay credentials must also be present. Without it, staff record offline payment with a receipt.
- Member self-checkout, contact self-checkout, notifications, public displays and other capabilities
  keep their own gates. Self check-in requires a configured geofence and an in-range reading; staff
  check-in supplies the alternative. There is no paid security tier.

Defaults and change authority are in [Limits](LIMITS.md), the module registry and the per-space
capability screens; [Features](FEATURES.md) and [Free and paid](../README.md#free-and-paid) describe the
same behavior. A provider can charge the operator for delivery or hosting without creating a member fee.

## Who it is for

- **Makerspaces and community workshops** that lend shared tools and need evidence-backed accountability.
- **Fab labs** that combine inventory, machine work, 3D printing, maintenance, events and bookings.
- **Tool libraries** that want the full loan lifecycle without installing machine operations.
- **Universities and institutional workshops** that need their own identity provider, organization-wide
  staff authority and multiple spaces on one deployment.
- **Networks, chains and hosting partners** that operate several isolated makerspaces while coordinating
  selected staff and cross-space stock movement.
- **Independent spaces with walk-in communities** that want attributable handovers without requiring every
  visitor to maintain a SpaceWorks account.

## Deployment options

### Self-hosting

Self-hosting is the primary documented deployment model. A first-run wizard for macOS/Linux and Windows checks
Docker, generates secrets, writes configuration, builds the stack, creates the first administrator and
makerspace, and prints the URL and credentials. Prebuilt backend and frontend container images are also
available. PostgreSQL, Redis, S3-compatible storage, background workers and migrations use Docker Compose.

Published main releases can trigger the optional server GitHub Actions runner after images and the
release are published, gated by `SPACEWORKS_DEPLOY=true`. Operators can also run
`bash scripts/update.sh --force`, optionally with `--version` for an exact release. See the
[required public-repository runner security settings](self-hosting.md#security). Updates are backup-first,
run readiness checks and can return application containers to the retained prior release if deployment
fails.

### Managed or partner-hosted operation

One SpaceWorks deployment can host many isolated makerspaces, so an institution, network or nearby partner
can operate it as a managed multi-tenant service. A deployment may also use managed PostgreSQL. The
`cloud` install profile selects the module set intended for a hosted box, and the tenant-migration workflow
lets a hosted space later move to its own server.

**Honest limits:** the shipped repository documents the managed-hosting architecture and a pilot-oriented
managed-PostgreSQL path; it does not document a first-party SpaceWorks hosting service. The documented free
tier is suitable for demos or pilots, not dependable production.

## Genuine differentiators

- **Evidence-backed handovers, enforced rather than suggested.** Photos, scans, remarks and audit entries
  are prerequisites of the loan workflow, not fields staff may forget to fill in.
- **One workflow regardless of interface.** Web staff, front desk, self-checkout, kiosk and `/control/`
  actions all reach the same state and inventory controls; chat channels only notify.
- **Per-makerspace encrypted integrations.** Each tenant owns its notification credentials; secrets are
  encrypted at rest, write-only and absent from frontend bootstrap data.
- **Modules that can be installed, hidden, restored and deliberately purged.** Uninstall retains history;
  destructive deletion is a separate confirmed action; selected unused apps can even be removed from a
  deployment's runtime surfaces.
- **Tenant data ownership and a real exit path.** Spaces can export data, move rows and files in an
  encrypted archive, approve which personal details travel, and cut over without two writable copies.
- **Multi-space authority without flattening tenant boundaries.** Organizations can grant selected actions
  across linked spaces while each makerspace keeps its own staff roster, inventory and audit scope.
- **Useful without mandatory member accounts.** External identity and named walk-in records preserve
  accountability even when built-in self-sign-up is disabled.
- **Open source and self-hostable.** SpaceWorks is licensed AGPL-3.0-or-later and can run on infrastructure
  controlled by the community using it.

## Product boundaries

Native Android and iOS applications are available from the release links shown on the hub. Connected
devices have signed identities and configured adapters; these do not grant staff authority or imply
support for every vendor's hardware. Doors are not opened by a public card scan. External cloud and
managed-hosting recipes have provider limits and operating requirements of their own.

Google Sheets report publishing through OAuth is not claimed here; CSV/XLSX export and supported
read-only Sheet import flows remain separate. The feature inventory describes the concrete shipped
surfaces, and the limits reference records the ceilings rather than promising an unlimited provider.
