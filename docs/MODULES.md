# SpaceWorks modules — what each one is, and what happens without it

Space Works ships **35 modules**: 6 **core** ones that cannot be switched off, 1 that is **on by
default** (`member_accounts`, owner decision #91), and the rest opt-in. The `backup` key was retired in
P1b (owner decision #111 Q2): backup and restore are platform duties. This page is the per-module reference the README links into — one entry
per key, saying what it is, what it puts on screen, what disappears if you do not install it, and what
happens to its data.

> **Derived from `backend/apps/makerspaces/module_registry.py`**, which is the single source of truth for
> module keys, defaults and dependencies. If you add or change a module there, update the matching entry
> here in the same commit. The rules modules must obey (install/uninstall/purge semantics, the `email`
> gate, two-level capabilities) are in `docs/INVARIANTS.md`, not here.

## Areas used by setup

Setup first asks whether to enable every area (default no). Yes selects all eight areas and still
asks their normal follow-ups in order; no asks yes/no about each area. Inventory & lending, Machines
and Reports default to yes; the other five default to no. An existing events/bookings edition defaults to its corresponding
area plus Membership, Online payments and Reports, preserving plans, checkout and reporting;
Inventory and Machines are off. Areas enable every child feature supported by the selected
modules and its feature prerequisites. Follow-up answers may turn off self-checkout, kiosk or
certification gating. Staff MFA is not a question: since release 2 it is required for every staff role
(platform rule; the old `security.staff_mfa_required` switch is retired).
The per-person accounts module (self sign-up, password/Google/Apple/GitHub/phone sign-in and the member
area) is always installed by setup; platform login-method switches and the provider selection still
govern sign-in availability. Membership adds plans, vouching, renewals and the mobile app.

| Area | Modules | Features |
| --- | --- | --- |
| Inventory & lending | `public_inventory`, `request_workflow`, `staff_admin`, `scanner`, `evidence_uploads`, `qr_management` (core); `guest_handover`, `asset_units`, `containers`, `bulk_import`, `stock_transfers`, `qr_print_batches`, `stocktake`, `devices` | `loans.enabled`, `loans.limits`, `loans.renewals`, `loans.kit_checklist`, `loans.reservations`, `loans.pickup_windows`, `loans.waitlist`, `loans.withdrawals`, `inventory.notify_when_back`, `inventory.expected_back`, `inventory.consumables`, `inventory.vendors`, `inventory.tobuy`, `inventory.warranty`, `inventory.self_checkout`, `inventory.contact_self_checkout`, `inventory.kiosk`, `stocktake.discipline`, `packs.import`, `charges.loans`; `payments.loans` with Online payments |
| Machines | `machines`, `machine_service`, `printing` | `machines.job_requests`, `machines.job_quotes`, `machines.batch_start`, `machines.pay_before_pickup`, `machines.time_booking`, `machines.sessions`, `machines.maintenance`, `machines.tobuy`, `machines.warranty`, `machines.certifications`, `machines.certification_reminders`, `machines.public_detail`, `machines.material_catalogue`, `machines.structured_intake`, `maintenance.reminders`, `maintenance.meters`, `maintenance.calendar_feed`, `charges.machines`, `notifications.delegated_recipients`; `payments.machines` with Online payments |
| Events | `events` | `events.api_read`, `events.certificate_designer`, `events.website`, `events.embed`, `events.short_links`, `events.online_delivery`, `events.anonymous_feedback`; `events.broadcasts` with Notifications and Email; `events.organization_audience`, `events.offline_checkin`, `events.invites`, `events.account_registration`, `events.ticket_types`, `events.promo_codes`, `charges.events`; `payments.events` with Online payments; `events.id_cards`, `events.ticket_designs`, `events.wallet_passes`, `events.orders`, `events.seat_holds`, `events.addons`, `events.series_passes`, `events.transfers`, `events.desk_collect`, `events.refund_override`, `events.venue_fees`, `events.applications`, `events.application_stages`, `events.attendance_confirmation`, `events.crew`, `events.crew_claims`, `events.checkin_lists`, `events.calendar_feed`, `events.shifts_feed`, `events.public_feed` |
| Bookings | `bookings` | `bookings.recurring`, `bookings.staff_grants`, `bookings.clone`, `bookings.staff_tools`, `bookings.confirmations`, `bookings.checkin`, `bookings.passes`, `bookings.api_read`, `bookings.website`, `bookings.embed`, `bookings.calendar_feed`, `charges.bookings`; `bookings.broadcasts` with Notifications and Email; `bookings.analytics`, `bookings.utilization_pdf`, `bookings.exports` with Reports; `payments.bookings` with Online payments |
| Membership | `membership`, `mobile` | `membership.auto_renew`, `membership.lifecycle_mail`, `membership.self_service`, `membership.self_export`, `membership.vouching`, `membership.application_form`, `membership.broadcasts`, the 14 release-2 lifecycle switches (`membership.plan_rules` … `membership.monthly_summary`), `mobile.push`, `mobile.watch_actions`, `charges.membership`; `payments.membership` with Online payments; `membership.id_programmes`, `membership.wallet_passes`; `membership.import_sheets`, `membership.id_programmes_import_sheets` |
| Online payments | `payments` | `payments.enabled` plus the online-payment feature of each selected domain |
| Reports | `reports` | `reports.saved_views`; `reports.event_pdf`, `reports.event_exports` with Events |
| Chat alerts | `telegram`, `slack`, `mattermost`, `discord`, `webhook` | Idle until URLs/tokens are configured |
| Always on | Six core modules, `notifications`, `email`, `member_accounts` | Every satisfiable child of `notifications`, `email` and `member_accounts`, `billing.reminders`, `charges.enabled`, `billing.documents`, `staff.invitations`, `presence.geofence`, `ui.delight`, `ui.easter_eggs` |

The source is `makerspaces/setup_areas.py`; registry module keys/defaults are unchanged. Inventory
off clears `loans.enabled` while keeping core. Optional-module uninstall retains all data. Charges,
receipts and offline settlement work without Online payments. See the
[follow-up questions and defaults](setup-for-makerspaces.md#area-follow-up-questions).

The change menu shows on/partial/off: numbers toggle, `a` selects all and `n` selects none. It asks
follow-ups only for newly enabled areas. `--all-modules` enables all eight areas and every supported
feature, keeping existing settings and security settings unchanged. Newly enabled areas get defaults;
`--without` exclusions still apply, and unavailable modules are reported rather than installed. Automation
can use `--areas=inventory,machines` (empty selects core and always-on services only), `--all-modules`,
`--without=key1,key2`, `--makerspace`, `--all-makerspaces`, and `--confirm-removals`.
Module-key CLI commands and legacy `setup_instance --profile` remain available; the questionnaire
offers neither profiles nor individual modules. Application reads JSON from stdin, validates through
the existing services and audited model paths, and never calls purge.

## The three levels

| Level | Who changes it | What it means |
|---|---|---|
| **Core module** | nobody | Always on. The Hard Rules make the loan spine *the system*: issuing hardware needs a box QR scan **and** an issue photo, so catalogue + requests + staff console + evidence + QR + scanner ship with every install. |
| **Module** | Space Manager or superadmin (console or CLI) | A whole capability. Installing adds its surfaces; uninstalling hides them and **keeps every row**. On the managed platform a module with a fair-use limit is installed by the superadmin only, and every purge (re-auth, preview, audited) is the superadmin's alone (#128 C-8, C-10). |
| **Feature** | Space Manager, or the module's manager with a settings grant | A switch *inside* a module, for something narrower than a whole capability. Inert while its parent module is off. |

## What "without it" actually means

Uninstalling a module does two things and nothing else:

- **The API refuses its endpoints.** Every gated view calls `require_module(makerspace, "<key>")`, which
  returns `400 {"module": "<key> is disabled for this makerspace."}`. A folded capability that is off
  (maintenance, To-Buy, warranty) answers `404 {"code": "capability_disabled"}` instead.
- **The frontend never renders the surface.** Bootstrap only publishes the workflows of installed
  modules, so the nav entry, page and buttons are simply not there.

**Your data is retained.** Uninstalling never deletes rows; reinstalling brings the surface back with its
history intact. Deleting rows is a separate, deliberate second command — see [Deleting a module's
data](#deleting-a-modules-data).

```bash
docker compose run --rm --no-deps backend --role management python manage.py list_modules
docker compose run --rm --no-deps backend --role management python manage.py install_module bookings
docker compose run --rm --no-deps backend --role management python manage.py uninstall_module bookings
```

A module another installed module depends on cannot be uninstalled until the dependant goes first, and
core modules cannot be uninstalled at all.

The registry contains 37 keys (35 in the main catalogue, with L22's `shop`, plus presence and analytics):
six core, member accounts enabled by default, and 30 opt-in. `maintenance` and `procurement`
were retired in release 2 and are capabilities now (see below); `backup` was retired in P1b.
SMS/WhatsApp are separate opt-in modules.
Migration 0097 preserves only previously enabled canonical WhatsApp installations;
new SMS/WhatsApp installations remain off. Existing operational channel conversion
preserves enablement/opt-outs and never enables platform sending. Module-list validation
uses the registry rather than scalar JSONField choices. Follow the independent
[conversion/replay/activation checkpoints](notification-reconciliation-rollout.md).

## Index

**Inventory** (always on): [public_inventory](#public_inventory) · [request_workflow](#request_workflow) ·
[staff_admin](#staff_admin) · [evidence_uploads](#evidence_uploads) · [qr_management](#qr_management) ·
[scanner](#scanner) · [asset_units](#asset_units) · [containers](#containers) ·
[bulk_import](#bulk_import) · [stock_transfers](#stock_transfers) ·
[qr_print_batches](#qr_print_batches) · [guest_handover](#guest_handover)
**Stocktake**: [stocktake](#stocktake) — **Machines**: [machines](#machines) ·
[machine_service](#machine_service) · [printing](#printing) —
**Per parent**: [maintenance, To-Buy, warranty and repairs](#maintenance-to-buy-warranty-and-repairs-switches-under-each-parent) —
**Events**: [events](#events) · [event_reimbursements](#event_reimbursements) — **Bookings**: [bookings](#bookings) —
**Membership**: [membership](#membership) · [presence](#presence)
**Notifications**: [notifications](#notifications) · [email](#email) · [sms](#sms) · [whatsapp](#whatsapp) · [telegram](#telegram) ·
[slack](#slack) · [mattermost](#mattermost) · [discord](#discord) · [webhook](#webhook) — **Reports**: [reports](#reports) · [analytics](#analytics) —
**Payments**: [payments](#payments) — **Accounts**: [member_accounts](#member_accounts) —
**Mobile apps**: [mobile](#mobile) · **Connected devices**: [devices](#devices) — **Shop**: [shop](#shop)

---

## Inventory

### public_inventory

[Read the public_inventory module reference](MODULES-INVENTORY.md#public_inventory).

### request_workflow

[Read the request_workflow module reference](MODULES-INVENTORY.md#request_workflow).

### staff_admin

[Read the staff_admin module reference](MODULES-INVENTORY.md#staff_admin).

One account per person (release 2): staff roles are granted to a person's existing account as
a staff-track membership, separate from any community membership in the same space; only the
superadmin grants the Space Manager role. No module turns on staff authority by itself: a role
grant does. Password sign-in remains available without Member accounts, Membership, Email,
staff invitations or MFA. (The staff sign-in and recovery screens move onto the one personal
sign-in in later release-2 lanes; until then they work as before.)

### evidence_uploads

[Read the evidence_uploads module reference](MODULES-INVENTORY.md#evidence_uploads).

### qr_management

[Read the qr_management module reference](MODULES-INVENTORY.md#qr_management).

### scanner

[Read the scanner module reference](MODULES-INVENTORY.md#scanner).

### asset_units

[Read the asset_units module reference](MODULES-INVENTORY.md#asset_units).

### containers

[Read the containers module reference](MODULES-INVENTORY.md#containers).

### bulk_import

[Read the bulk_import module reference](MODULES-INVENTORY.md#bulk_import).

### stock_transfers

[Read the stock_transfers module reference](MODULES-INVENTORY.md#stock_transfers).

### qr_print_batches

[Read the qr_print_batches module reference](MODULES-INVENTORY.md#qr_print_batches).

### guest_handover

[Read the guest_handover module reference](MODULES-INVENTORY.md#guest_handover).

### To-Buy (was `procurement`)

A capability now: `inventory.tobuy` and `machines.tobuy`, see
[the per-parent switches](#maintenance-to-buy-warranty-and-repairs-switches-under-each-parent) and
[the To-Buy reference](MODULES-INVENTORY.md#procurement).

## Stocktake

### stocktake

[Read the stocktake module reference](MODULES-INVENTORY.md#stocktake).

## Machines

### machines

[Read the machines module reference](MODULES-WORKSHOPS.md#machines).

### machine_service

[Read the machine_service module reference](MODULES-WORKSHOPS.md#machine_service).

Finalized consumable costs accompany their service sources and are removed with them
during module purge; independent manual pool usage and its recorded costs remain.

**One "Request a job" flow for every machine type (release 2, L12; #140–#142).** Members of the
space who are checked in pick a machine type that takes jobs, upload files in the formats that
type accepts, add material and notes and confirm the pickup, failure and ownership terms. Every
type shares the same queue (live "#N in queue", "You're next", an ETA that respects opening
hours for attended machines), quotes the member approves (`machines.job_quotes`, per type),
payment at completion or before queueing, failure outcomes (a space fault re-runs free at the
front; a member fault follows the type's failure charge), pickup codes, reminders and a staff
"Not collected" from day 14. Staff work a per-type queue board (reorder, urgent pin, assign,
start, batch start with `machines.batch_start`, finish, collect). The 3D-printer form is an alias
of the same flow. Off (`machines.job_requests`): no member submits a job; staff keep every job.

**Metered machine sessions (release 2, L23; #158).** With `machines.sessions` on, every machine has
a session QR (Machines › a machine › Sessions). A member who is checked in, certified for the type
and not blocked by a booking, lockout or downtime scans it, sees the hourly rate, minimum and
longest session, taps Start and later Stop; staff start, stop and check sessions for members from
Machines › Sessions, and an integrated machine's own job reports open and close one. A forgotten
session stops itself at the type's longest session (type Settings, default 4 hours), at check-out
or at closing time and waits for a staff check, where the time can be corrected with a reason
before it is confirmed. The charge follows the machine type's hourly rate on the rate card, frozen
when the session started, as a pending charge staff settle. Reports: sessions by member and
machine, utilisation, busiest days and hours, idle machines and flagged sessions. Off: no session
screen, route or sweep; everything recorded is kept. A purge deletes sessions and their
corrections only.

### printing

[Read the printing module reference](MODULES-WORKSHOPS.md#printing).

### Maintenance (was `maintenance`)

A capability now: `machines.maintenance`, see
[the per-parent switches](#maintenance-to-buy-warranty-and-repairs-switches-under-each-parent) and
[the maintenance reference](MODULES-WORKSHOPS.md#maintenance).

## Maintenance, To-Buy, warranty and repairs: switches under each parent

Owner decisions #97 and #128 C-9 retired the `maintenance` and `procurement` module keys and
put what they switched — plus warranty, which never had a key — **under each parent** as
two-level capabilities, each its own switch. Machine ones sit under `machines`, room ones
under `bookings`, and item ones in the parentless inventory family (labelled "Inventory",
like `inventory.kiosk`). Rooms get no To-Buy or warranty switch in release 2 (#137 Q-C3).
The Django apps stay internal and separable (`TOMBSTONED_APPS` still removes them).

| Capability | Parent | Default | What it switches |
|---|---|:--:|---|
| `machines.maintenance` | `machines` | | Machine maintenance schedules, logs, documents, overdue list, calendar feed, reminders and the dashboard/report sections; machine work orders, the downtime ledger and maintenance lockout (L12) |
| `machines.tobuy` | `machines` | | To-Buy rows for machine consumables (the `printing` stream) and automatic filament low-stock drafts |
| `machines.warranty` | `machines` | | Warranty records and documents on machines |
| `inventory.tobuy` | — (Inventory) | | To-Buy rows for inventory items (the `hardware` stream), reorder drafts and, later, the shop |
| `inventory.warranty` | — (Inventory) | | Warranty records and documents on inventory assets |
| `machines.repairs` | `machines` | | Repair jobs on machines (L16): the Repairs queue, triage onto L12's work order, the technician directory, sends by email/chat, visits, parts, quotes and ledger payouts. Requires `machines.maintenance` |
| `machines.issue_reporting` | `machines` | | Members report a problem from their own machine job; the type-scoped Machine Manager and the Space Manager are notified (works without repairs: notify only) |
| `inventory.maintenance` | — (Inventory) | | Maintenance schedules and logs on inventory items and units, and their work orders (L16) |
| `inventory.repairs` | — (Inventory) | | Repair jobs on items and units, as for machines. Requires `inventory.maintenance` |
| `inventory.issue_reporting` | — (Inventory) | | Borrowers report a problem from their own loan (account-less borrowers by their verified email, #80); the Inventory Manager and the Space Manager are notified |
| `bookings.room_maintenance` | `bookings` | | Maintenance schedules and logs on bookable rooms, and their work orders (L16) |
| `bookings.room_repairs` | `bookings` | | Repair jobs on rooms, and taking a room out of service (block new bookings, the default, or warn). Requires `bookings.room_maintenance` |
| `bookings.issue_reporting` | `bookings` | | Bookers report a problem from their own booking; the Booking Manager and the Space Manager are notified |
| `inventory.maintenance_reminders` | — (Inventory) | ● | Tell the Inventory Manager (the `hardware_requests` family) the day before item or unit maintenance is due and the day after it goes overdue. Requires `inventory.maintenance` and Notifications; off sends nothing and keeps every schedule |
| `bookings.room_maintenance_reminders` | `bookings` | ● | The same for room maintenance, to the Booking Manager (the `bookings` family). Requires `bookings.room_maintenance` and Notifications |

`maintenance.meters`, `maintenance.calendar_feed`, `maintenance.reminders` and
`notifications.delegated_recipients` keep their keys and now sit under `machines`, each
requiring `machines.maintenance`.

- **One To-Buy list, two switches.** A row's stream is its domain: `printing` rows belong
  to `machines.tobuy`, `hardware` rows to `inventory.tobuy`. A parent whose switch is off
  hides its rows (its routes answer 404, its rows stay) and takes no new ones; the other
  parent's rows are untouched. The list is gone only when both are off.
- **One warranty app, two switches.** A warranty on a machine follows `machines.warranty`,
  one on an asset `inventory.warranty`.
- **Off means off.** Every folded route answers **404** while its switch is off; no
  reminder, alert or low-stock draft is produced; nothing shows in the console. Turning the
  switch back on restores everything.
- **Upgrade.** Migration `makerspaces/0111` keeps every space exactly as it was:
  `maintenance` installed → `machines.maintenance`; `procurement` installed →
  `inventory.tobuy`, plus `machines.tobuy` where `machines` is installed; warranty rows on
  assets/machines → the matching `*.warranty`. The old keys are stripped from stored rows and
  audited as `makerspace.module_retired`. No row of any table is changed.
- **Purge.** Switching off keeps the data. Deleting it is the separate superadmin
  `/control/` action **Purge capability data** (recent re-authentication, a preview of the
  rows, the key typed back, audited `makerspace.capability_purged`), split per parent:
  purging `machines.tobuy` never deletes an inventory row.
- **Who switches them.** The Space Manager; a module's manager with that module's settings
  grant (see [Settings authority](INVARIANTS.md#settings-authority-release-2-lane-l17-101-128-c-11)).
- **Repairs and issue reporting (L16).** A report needs its area's `*.issue_reporting`
  switch; everything after it needs `*.repairs`, which needs the area's maintenance switch
  because the repair job is the L12 work order. With repairs off a report is notify-only and
  the manager fixes, closes or rejects it. Off answers 404 and keeps every report. Purging
  `*.repairs` deletes that area's issues with their history, photos, technician sends and
  parts; `*.issue_reporting` owns no rows of its own; the shared technician directory goes
  only with a tenant purge. Purging `inventory.maintenance` / `bookings.room_maintenance`
  deletes that kind's schedules, logs and work orders (rooms also their outages). See
  [Repairs and technicians](INVARIANTS.md#repairs-and-technicians).
- **Repairs reports (RP-5).** While any `*.repairs` switch is on (the work-order list also with any
  maintenance switch), Reports offers open and overdue work orders, technician workload, repair time
  per area and parts used, with CSV export. A Technician sees their own jobs; each manager sees their
  own area (a Machine Manager only their machine types).


## Events

Public makerspace pages and global organization pages do not introduce module keys. A public,
servable makerspace may publish an informational `/<handle>` page with no content family installed.
Its inventory, event, booking and membership sections still obey their existing module gates.
Only a local Space Manager edits a makerspace page; organization profile governors edit their own
global page. Platform accounts do not edit these pages.

The existing Events module owns `/e/<public_token>` and enhanced event websites. `events.website`
controls the website builder; a basic public event may use its short URL without website release.
Saving content changes a draft, and release selects a complete immutable snapshot. Uninstalling
Events hides these surfaces while retaining snapshots, session identities and private bytes. An
explicit Events data purge removes that venue's history and queues retryable private-byte deletion;
unrelated makerspace and global organization pages remain. Past organization cards expose only the
approved archive fields and do not reopen expired event websites.

### events

[Read the events module reference](MODULES-WORKSHOPS.md#events).

**Paid ticketing v2 (release 2 L6).** Eight capabilities, all off by default, keep their data when
turned off: `events.orders` (with `events.seat_holds`, `events.addons`, `events.series_passes` and
`events.transfers` under it), `events.desk_collect`, `events.refund_override` and `events.venue_fees`.
A buyer must be signed in; each seat becomes one registration for one attendee account, claimed by
signing in with the address it names. Money owed is one `event_order` (or `event_venue_fee`)
`Payment`, events income, recorded by `charges.events`; every refund is a staff-approved refund
case. Registration and booking confirmation emails carry an `.ics` invite (and, with
`events.ticket_designs`, the ticket PDF) and "add to calendar" links; the private join link never
rides the invite. A purge of Events deletes orders, seats, dues and holds with their events;
the payment ledger rows stay (they are permanently core).

**Applications, review stages, attendance, crew and check-in lists (release 2 L21a).** Six
capabilities, all off by default, keep their data when turned off. `events.applications` opens the
hackathon admission engine (form, review, offers, RSVP, waitlist) on any one-off event, without
teams or submissions; `events.application_stages` adds review stages, each with its own reviewer
panel, criteria, blind switch and 1 to 20 reviews per application, a seeded reviewer assignment and
an "advance" decision. Paid places are still charged after the place is confirmed.
`events.attendance_confirmation` lets staff ask "Are you still coming?" (never automatically, 12
hours apart); with the per-event switch "free the place on No" a free place goes to the waitlist and
a paid one is cancelled under the refund policy, any refund waiting for staff approval.
`events.crew` adds the organising crew: a reviewed sign-up link, free crew places outside capacity,
a catering count and an opt-in public crew section; `events.crew_claims` (with Event reimbursements)
lets crew claim expenses. `events.checkin_lists` adds swag, meal and workshop lists beside entry
check-in. Turning any of them off hides its screens and its routes answer 404; a purge of Events
deletes this data with its events.

**Programme checkpoint (2026-10-18, `f1ef7736`).** Hackathons
are features inside Events, not a separate module. Five declared switches are ordinary per-space switches, off for a new space, that a Space Manager may turn on:
`events.hackathons`, `events.mentoring` (since release 2 it no longer requires hackathons: Mentor Desk
works on any event), `events.mentor_rounds` (requires mentoring and hackathons), `events.volunteering`, and `events.project_gallery` (requires
hackathons). Release 2 adds one more, off and requiring hackathons: `events.pairwise_judging` (a third
judging mode). KiCad files stay download-only (owner, 2026-10-29). Each hackathon also needs its disabled-by-default event config enabled.
Volunteering can serve ordinary events. Schema, routes and generated API exist; live
provider installation and acceptance remain incomplete. See the [runbooks](events/README.md)
and [exact integration closure ledger](events/integration-status.md).

Choosing the Events area in setup does **not** switch these five on: `setup_areas.py` lists
them (with every reserved key) in `EXPLICIT_OPT_IN_FEATURES`, so `features_for()` leaves them
off and a space opts in to each programme switch on its own.

Authored workflows cover applications/review/private decision release/RSVP/waitlists,
three team modes plus opt-in finder, contributor shifts/hours, Mentor Desk, immutable
upload/link submissions, weighted or top-three judging, results/gallery, v2 badge
credentials, certificate verification/library/bulk/print, forms v2 and operations tools.
Account-owned Saved details is independent of Events and host membership; its vault is
not organizer-readable.

Staged forms are part of Events (no module key). Organisers publish forms tied to a
stage: application, shortlisted, accepted/RSVP, pre-event or post-event. Application-stage
forms are answered with the signup itself and are saved in the same transaction, so a
required form left out refuses the whole registration or application. A required form
set to "block" stops RSVP, check-in (including offline-synced check-ins) or a travel
claim until it is complete; "warn" lets the member continue and sends a reminder. Stage
uploads count against per-member and per-event quotas and expire a set number of days
after the event (`EVENT_STAGE_*` settings). An Events purge deletes stage rows after
keeping their file-cleanup locators; a travel-support-only purge keeps them.

Feature disablement removes its gated live actions/reads and retains definitions, history
and private objects. Events uninstall retains those rows; deployment tombstoning removes
runtime surfaces while retention/PII/purge/backup declarations survive. Events purge uses
the child-before-parent graph and removes owned programme rows and keys, preserving the
core money ledger, global account vault and foreign profile bytes. Every cleanup that
removes an asset key (retention and purge custody alike) first proves the key is gone --
all versions, delete markers and multipart uploads -- and then writes a durable, FK-free
`SubmissionStorageCleanupReceipt` (key hash and counts, never a locator). A daily
reconciliation (`event-storage-reconcile`) corrects event usage drift from the live asset
rows, audited as `event.asset_usage_reconciled`. Imported public/consent/grant/credential state
is inert until fresh target-side authorization; imported assets are charged to the target's
event pool exactly once, when that reconciliation first sees them (the obligation row is the
idempotency key).

Managed hackathon storage is a separate decimal **25 GB per event** pool (25,000,000,000
bytes); self-host can configure a byte budget or unlimited event pool. File/group/submission
bounds and used+reserved accounting still apply. Files expire 365 days from the recorded
results/cancellation/fallback anchor without deleting records/hashes; corrections do not
extend expiry. Live expiry does not erase older backup archives. [Media limits](events/media.md)
and [operator notes](events/operations.md) explain pending storage/scheduler adapters.

Events can run with membership and the online payments rail off. Members-only remains the
default audience; opt-in account registration, invitations, ticket types and promo codes
support public workshops. Paid tickets still create core ledger charges for offline settlement.

Opt-in `events.organization_audience` adds “Participating organizations”: active members of
this event's organizer organizations and venue owner, directly or through their owned makerspaces,
can register without joining the venue. Manager/affiliate links do not qualify. Public event
labels name the usable organizations; membership loss leaves existing tickets readable.
Portable imports block this audience until an authorized editor explicitly confirms the target
organizations and ownership; ordinary edits and cloning cannot clear the block. Deployment
backups preserve the original graph. Uninstall/purge retain the core money ledger.

Event managers and organization organizers can invite staff to one event or series with
selected permissions for details, registrations, invitations, check-in and scheduling.
These helpers use member accounts and can sign in to see only their granted events; grants confer no makerspace
role or actions. Invitations expire after seven days and revocation applies immediately.
Grants and invitation credentials are excluded from portable exports and imports;
the destination must issue fresh access. Uninstall retains the rows, while events purge
deletes them, including when the events app is tombstoned.

The ordinary event tools also include draft duplication, validated registration-answer edits,
five-minute cancellation undo, feedback starter templates, owned ticket PNG downloads and
Google Calendar links. They use the Events module and the relevant staff permission; there
is no additional feature switch. Duplication copies owned cover images to fresh keys and
never copies participation or grants. Undo refuses historical charges, consumed invitations
or discounts, closed admission and unavailable confirmed seats. Public registration counts
can be hidden per event. Purge removes these event fields and copied images with their
existing event records; uninstall retains them.

Opt-in `events.certificate_designer` adds private artwork uploads, positioned name boxes
and server PDF previews in the Events drawer. Every save creates an immutable revision;
issued certificates freeze the selected design, so later changes never alter pending or
retried certificates. Turning the feature off removes editing and preview access while
existing certificate snapshots remain readable through their ordinary authorized path.
Artwork, revisions and certificates are removed by an Events purge in dependency order.
Legacy display badges use the shared positioned layout engine and remain free of contacts
and bearer QR codes. The separate v2 desk-badge workflow permits only its typed opaque,
event-bound check-in credential QR; it requires authenticated online resolution and
generation-bound confirmation. It never permits contact fields, arbitrary bearer URLs or
offline v2 admission. Custom answers require registration
management plus the tenant audit permission. These badge changes use the existing Events
module rather than a new feature switch.

Opt-in `events.broadcasts` requires Notifications and Email. Staff with event registration
authority compose email campaigns filtered by registration status and attendance, review
drafts, send and cancel from the Events drawer. Only verified eligible accounts receive
mail; preferences, suppression and quiet hours apply. With a saved personal category selection,
envelopes own channels including email/fallback; otherwise the campaign worker owns email
and extra-channel envelopes pre-skip it to avoid duplicate mail. Staff rooms
never receive campaign bodies. Delivery history survives uninstall;
events purge removes campaigns and their event-source outboxes. Imported unfinished
campaigns are cancelled and cannot resume. Bulk email-bound invitations reuse Events
invites and email only an event link; the signed-in participant verifies their email to
use an invitation without entering a code.

`events.api_read` is off by default. Only a platform superadmin can grant
`events:read`, `participants:read` and `participants:attendance:read` to a server
client bound to one makerspace. Read routes always require a valid HMAC signature,
even when public-API enforcement is optional. Participants require event and
participant scopes; attendance needs the extra scope. Contacts, custom answers,
payment data and bearer credentials are excluded. Without the feature reads are
refused. Uninstall retains history; purge uses the existing Events retention graph.
Bookings reuses the core target/signature/keyset mechanisms through typed adapters.

Opt-in `events.website` adds curated event and series pages: introductions and page logos,
speakers, tracks, rooms, sessions, sponsors, FAQs and links. Detail editors manage sections
and private images; schedule publishers manage programme times, live delays and website
release. Existing events start without a released website. Publishing an event releases its
saved page only when “Publish website with event” is selected; pages can then be released
or unreleased independently. An occurrence inherits its series page until an editor saves
an independent, initially unreleased copy. Event duplication copies content and images to
fresh private keys, with no copied release or live delays.

Opt-in `events.embed` requires `events.website`. A released, public, unexpired event can
appear as a backend HTML card only on the makerspace's exact HTTPS framing origins,
configured in Public site settings by a makerspace manager. The empty list disables
embedding. Ordinary SPA pages deny framing. Public website images are private stored
objects read through the live visibility gate, not public bucket URLs. Existing event
covers retain their public behavior. Deployment-local discovery, canonical sitemaps and
crawler share cards respect public visibility and directory consent; discovery does not
require an enhanced page to be released. Uninstall hides the enhanced surfaces and retains
the rows and objects; Events purge removes both. Portable imports retain editorial content
and private objects but reset page release and framing origins for target-side review.

#### Public event surface (release 2, L1)

Four answers decide who reaches an event, and none of them is a new lifecycle state:

* **Who can see it** is `is_public` (only your team, or anyone with the link).
* **Who can find it** is `Event.listing`: *listed* events appear on the events page, Discover,
  organisation and Pages collections, member profiles, series listings and the sitemap;
  *unlisted* events appear on none of them and their pages, share cards and API answers carry
  `noindex, nofollow`, but anyone holding the link (`/events/<token>`, `/e/<token>`, a short
  link) can open them and sign up. A private event is never listed. A series' `listing` is
  copied to occurrences when they are generated; each occurrence then owns its own.
* **Who can sign up** is the unchanged `registration_audience`.
* **Page state** (`page_state`: live or offline) takes a published page down everywhere
  public, as a uniform 404, without cancelling or unpublishing the event.

Opt-in **`events.short_links`** (off) gives an event one live `/e/<7-char base62>` code beside
the long address, made on request by staff holding the event's publishing authority. The
code follows the event (slug and host changes keep it working); regenerating retires the old
code at once, and a retired code is never issued again. Resolution is rate-limited and has
exactly the public event gate. Visits are one number per event per local day, counted for
people (not link previews), never who visited. Off: staff routes and codes 404; codes are kept.

Opt-in **`events.online_delivery`** (off) marks an event in person, online or hybrid. The join
link is stored encrypted and is released only to a confirmed registrant: their ticket, their
confirmation email and their own calendar. It is never on a public page, share card, embed or
audit row. Off: no mode chip, no link anywhere, editor fields hidden; the link is kept.

**`events.embed`** also serves a styled card at `/embed/<space>/<event token>/`, framable only
by the origins in the space's own event allow-list (`EventEmbedPolicy`, off by default; set in
the events settings by the Space Manager, or the Event Manager with the events grant).
Sign-up opens the event in a new tab.

Every public event has a share image (`share.png`) used when it has no cover. The member ticket
shows a venue map link for in-person and hybrid events. The Event Manager switches the event
PDF and event exports (`reports.event_pdf`, `reports.event_exports`) while holding the events
settings grant. A staff member who runs events in several spaces picks the host space when
creating an event.

**Communications and analytics (release 2, L2).** The broadcast composer saves drafts as
you type (versioned, so a second tab cannot overwrite silently), shows delivery tallies by
best outcome (delivered, waiting, failed, skipped; never who), and "Send now" holds the
message five seconds with a visible Undo; after that the accepted-mail rule applies.
Opt-in **`events.broadcast_templates`** (off) adds 13 starter templates (subject, message,
audience and design) and three more brand designs: accent band, photo header and letter.
Opt-in **`events.approval_digest`** (off) emails each organiser one summary every 30 minutes
while sign-ups wait for approval (titles and counts only; nothing when nothing waits).
A staff removal is announced to the member only after its five-minute undo window has
passed (an undone removal sends nothing), a member who verifies a new email gets their
upcoming tickets again, a day-ahead reminder skips sign-ups from the last 12 hours, and a
confirmation for an online or hybrid event carries the join link. Event analytics add
arrivals by 15-minute window, the check-in method split, feedback choice charts (written
answers are never charted), waitlist conversion, series turnout and short-link visits; the
platform view adds organisation cross-event totals with counts under 10 withheld.
**`events.anonymous_feedback`** (on) lets a feedback form promise anonymity while
certificates are off: answers keep no registration, account or IP. With it off (or unticked
on the form) feedback is identified and needs sign-in. A form already promised anonymous
accepts nothing while the switch is off.
Opt-in **`events.mentor_chat_alerts`** (off) posts new Mentor Desk help requests to the
team chat rooms an organiser picks, only while a mentor is on shift: outbound text with the
topic, team name and a Mentor Desk link, no buttons, quiet hours respected.
Opt-in **`events.submission_integrity`** (off) checks each project snapshot's GitHub
repository for commits from before kickoff and shows an information chip to judges and
organisers. It never disqualifies, hides or scores; GitHub failures leave no flag.
Opt-in **`events.organization_sender`** (off) shows a co-hosting organisation's name ("Club
via Space") and Reply-To on event email; the space's address, provider and email gate stay.

Not built, by decision: **guest RSVP** (registration always needs an account, #71), and
**organisations host only through a space they own** (#71): an organisation never hosts an
event without a makerspace.

## Bookings

Opt-in `bookings.website` adds resource detail pages with curated rules, amenities, FAQs,
links, sponsors and private gallery images. Existing active/public resources retain their
core catalogue and booking behavior when the feature is off or the page is unreleased.
Only explicitly published sections and their images appear after a separate website
release. Resource `edit_details` staff edit content/images; `publish_page` staff release
or unrelease a saved revision. Neither permission can make a private resource public or
activate it. Private previews are separate authorized, no-store reads.

`bookings.embed` also defaults off and requires `bookings.website`. Released resource
cards can be embedded only from the makerspace's exact HTTPS framing-origin allow-list;
ordinary site pages continue to deny framing. Share cards use the existing public cover,
never a private gallery image. `/discover/bookings` and sitemaps honor directory consent
and verified custom domains separately from direct resource access. New discovery is
paginated; the existing tenant resource list remains an array.

Disabling either feature retains editorial data. Bookings module purge removes pages,
sections and private gallery objects with their resource; whole-tenant purge also collects
them. Resource clones copy assets into independent keys and start private/unreleased.
Portable imports retain editorial content but reset release and framing trust for target
review; deployment backups preserve the original graph.

Opt-in `bookings.broadcasts` requires Notifications and Email and defaults off. Resource
reservation managers can compose, preview, queue and cancel email campaigns for pending
and/or confirmed bookings starting in a bounded future window (maximum 366 days). Each
account receives a personal envelope when a bookings-category selection exists; otherwise the
batch worker retains verified-address email, never both. Requester
settings, membership consent where present, personal preferences, suppression, quotas and
quiet hours apply. Campaign bodies never enter staff rooms; the legacy email path remains outside
digests. Import preserves history
but cancels unfinished campaigns and removes source outbox authority.

Booking reminders also reach eligible account-only bookers, with no Membership, Events,
Presence or online-payment dependency. Old queued reminders are invalidated by cancellation
or a changed booking window/revision, including entries in already-built daily digests.
Unverified email and existing membership opt-out still suppress delivery. Bookings purge
removes campaign/delivery history and booking-source outboxes; the core ledger remains.


### bookings

The Requests queue spans only resources the actor manages. Reject requires a reason; cancel accepts
one. Place galleries hold up to 12 public photos; Hosted at uses public venue matches/host-cover
fallback. Staff or the exact account owner can record one check-out with typed outcome and an
append-only encrypted remark; non-all_good outcomes require a remark and open an issue for triage.
Requester notifications now default on; the upgrade preserves audit-recorded tenant choices and
resource overrides. Bookings purge includes departure/issue rows and gallery objects.

Bookings accepts authenticated active accounts without installing `membership`. Existing
memberships retain their waiver requirement; booking in advance never requires presence.

[Read the bookings module reference](MODULES-WORKSHOPS.md#bookings).

`bookings.confirmations` (off by default) adds owner-only confirmation details, a private QR
PNG, Google Calendar link and single-booking ICS download. `bookings.checkin` (also off,
requires confirmations) lets authorized staff resolve that resource's QR and separately
confirm or reverse arrival. It requires no events, membership, presence or online-payment
module. Arrival is recorded from 30 minutes before start through end and remains independent
of completion and charges. Active arrival must be reversed before cancellation, rescheduling
or no-show; completion retains it and a later correction never reopens the booking.
Switching these features off hides their routes without deleting history. Bookings purge
removes arrival history before reservations; portable archives retain historical facts and
regenerate QR credentials. These are arrival counts, never measured-use duration.

`bookings.passes` (off by default, requires confirmations) adds printable PDF passes,
a resource pass-designer tab and sample previews. Only display name, resource, booking
window and an optional booking reference can print. Answers, notes, contacts and QR
credentials are always refused, including in older stored layouts. Owners download their
own confirmed/completed pass; staff need check-in permission and a current recorded
arrival. Template editing alone grants no scanner printing or roster access. Layouts stay
on uninstall and travel as bounded resource configuration; Bookings/tenant purge removes
them with resources. No artwork or PDF objects are stored. Without this feature,
confirmations and arrival continue independently and pass routes refuse.

`bookings.staff_grants` (off by default) delegates selected operations for one resource to
member accounts, without creating tenant staff identity.
Its four permissions cover descriptive editing, reservation management, check-in and page
release. Pricing, rules, machine links, activation, visibility policy, finance and further
delegation retain tenant permissions. Invites expire after seven days and recheck the
sender's current authority when accepted. Without the feature, existing tenant booking
management continues and resource grants confer no access. Uninstall retains history;
Bookings purge deletes resource staff grants/invites along with resources and reservations,
while preserving the core payment ledger. Portable imports require staff to reissue grants.


`bookings.clone` (off by default) lets tenant booking managers create an active,
private copy of resource configuration with independent cover images. Protected
booking rules start at defaults; copying them requires makerspace-management
permission. No bookings or staff access are copied. `bookings.staff_tools` (off by
default) adds reservation note/answer edits, validated time moves and exact undo of
cancellation within five minutes. Moves obey the existing and proposed cutoffs and
current rules; undo refuses any historical charge or changed admission state. Neither
feature grants payment, certification-override or identity-reassignment authority.
Without these features the ordinary existing workflows continue. Cancellation
provenance and restored lifecycle notifications remain part of booking history;
uninstall retains them, and ordinary Bookings purge removes resource/reservation
history and their owned cover images while preserving the core payment ledger.


## Membership

### membership

[Read the membership module reference](MODULES-WORKSHOPS.md#membership).

**Member cards (release 2 L3).** Member cards ride this module: a free card designer (space default,
per-plan and per-title designs, approval by a Space Manager when switched on), cards issued when a
membership starts, PNG/PDF downloads, bulk PDF/ZIP/email jobs (files kept 7 days), a desk scan that
only identifies, and an optional public check page. There is no fee on any card. Turning the module
off hides them; a purge deletes cards, designs, card settings and their stored files.

### presence

Time-limited member and guest check-in and the public current-presence TV display. Independent,
opt-in and dependency-free; self check-in needs an enabled/configured geofence and an in-range
browser reading. GPS remains spoofable; authorized staff can check in members/walk-ins without it.
The presence service and bootstrap share 1/2/3/4 h defaults (configured presets win).
Status is working, visiting, attending_event or guest. Names and personal
opt-out are controlled separately; public project/event titles need their own live visibility.
Expiry produces a personal renewal notice, default in-app/push. `/m/<slug>/now` displays current
rows only; it publishes no account IDs, contacts, coordinates or history.

Without it: session, roster, privacy and TV routes refuse and the module-gated UI disappears.
Uninstall retains history; purge deletes `PresenceSession`, `PresenceSettings` and
`PresencePreference`; portable import drops them. `makerspaces/0096` installs presence on all
existing makerspaces, including archived ones, preserving other choices; reverse is a no-op.
New makerspaces still opt in. Current-session exposes personal opt-out/name policy even when empty.
Space Managers configure privacy in the module-gated settings section. The expiry category still
lacks feature-enum/editor integration; see the presence rule in [INVARIANTS.md](INVARIANTS.md).

### member_accounts

[Read the member_accounts module reference](MODULES-WORKSHOPS.md#member_accounts).

This controls the community account ecosystem. A person who holds staff roles uses the same
account (one account per person, release 2); the platform account's password door and recovery
stay independent, and member self-service recovery never resets a platform account.

## Notifications

### notifications

[Read the notifications module reference](MODULES-PLATFORM.md#notifications).

Personal delivery uses explicit-recipient envelopes and verified provider endpoints, with
multi-select category preferences and email fallback. Space Managers configure encrypted channel
credentials under Communication channels; staff manage their own connections under My channels,
and a member Channels tab exists. Manager defaults prefer verified Telegram, otherwise email;
other accounts default email/in-app. Tenant matrix/module/suppression rules still apply. WhatsApp
is personal-only with `twilio|meta` providers and an independent default-off `whatsapp` module;
both providers are registered/mounted and the former missing-module blocker is resolved.
SMS uses Twilio under its own default-off module. Physical sender/STOP history, BSUID correlation
and device push live beneath canonical envelope delivery. The inbox module is optional.
Member JWTs reach exactly the six personal routes and OAuth uses authenticated challenge verification.
Release 2 (L2) adds: **`notifications.inbox_snooze`** (off) to snooze an inbox message for
up to 30 days or archive it (off: every row shows again, nothing lost);
**`notifications.web_push`** (off) for opt-in browser notifications of new inbox messages
(W3C Web Push with the deployment's `WEB_PUSH_VAPID_*` keys; only public push services are
accepted as endpoints); **`notifications.escalation`** (off) re-pings the space's general chat
rooms and opted-in browsers once when an urgent staff notice is unseen for 30 minutes; and,
for every space, a chat room whose last five deliveries all failed is switched off with a
staff notice. Staff-grant invitations for events and bookable spaces, and organisation
invitations given an optional invitee email (#145), are also offered on the invitee's own chat
channels when the address belongs to a verified account (never a room).
Remaining delivery limits are recorded in the
[delivery contract](notification-contract.md#integration-limits-in-this-tree). Security mail and
mandatory-mail exemptions keep their own delivery rules.

### email

[Read the email module reference](MODULES-PLATFORM.md#email).

### sms

Default off independently of the optional inbox and OTP SMS. Verified account-only owners
with a current tenant tie may consent; revoked/restricted accounts remain excluded.

[Read the SMS module reference](MODULES-PLATFORM.md#sms).
Provisioning, verified callbacks, quotas and recovery: [messaging operator guide](messaging-channels.md).
With reports enabled, communications health includes scoped SMS delivery cohorts,
segment estimates/bills and a labelled current consent snapshot. Platform metering
separates notification usage from OTP counts; [measurement notes](SOURCE-MAP-REPORTS.md#communications-and-messaging).

### whatsapp

Default off and personal-only, with canonical Twilio/Meta providers. The combined registry
contains this key, removing the former Meta missing-module readiness blocker. Existing operational
installations need explicit conversion preserving enablement and opt-outs; platform senders stay off
until the operator enables them.

[Read the WhatsApp module reference](MODULES-PLATFORM.md#whatsapp).
Provisioning and the shared sender correlation barrier: [messaging operator guide](messaging-channels.md).
With reports enabled, communications health includes scoped WhatsApp progress and
delivery/read rates plus a labelled current consent snapshot. Platform usage exposes
counts only; [measurement notes](SOURCE-MAP-REPORTS.md#communications-and-messaging).

### telegram

Room alerts plus provider-proven private account messages. The webhook accepts only secret-checked
private `/start` linking; every decision callback is acknowledged and ignored, no keyboard is sent.
Rooms prefer the contract bot token; personal delivery requires it and current endpoint consent.

[Read the telegram module reference](MODULES-PLATFORM.md#telegram).

### slack

[Read the slack module reference](MODULES-PLATFORM.md#slack).

### mattermost

[Read the mattermost module reference](MODULES-PLATFORM.md#mattermost).

### discord

[Read the discord module reference](MODULES-PLATFORM.md#discord).

### webhook

[Read the webhook module reference](MODULES-PLATFORM.md#webhook).

## Reports

### reports

[Read the reports module reference](MODULES-PLATFORM.md#reports).

| Feature | Default | What it adds |
| --- | --- | --- |
| `reports.saved_views` | ON | Personal server-side report filters and columns, with optional manager-published makerspace sharing. Opening a view rechecks both reader and owner authority. |
| `reports.event_pdf` | OFF | Audited post-event analytics PDF using the event-attendance builder; requires Events, full event management and tenant audit permission. |
| `reports.event_exports` | OFF | Registration and feedback CSV/XLSX plus previews; requires Events, event registration management and tenant audit permission. |

Event analytics in the drawer uses one tenant-local event subject through the existing
report registry. New exports cannot be scheduled or aggregated across tenants or an
organization. Subject-filtered saved views recheck both owner and reader. Feature off
refuses its export; it retains event history. Manual PDF files are generated on demand
and add no stored objects; events purge removes the underlying history, not the core ledger.

Membership reports add counts-only join-month cohorts and retention at 3/6/12 months (or a chosen
anniversary), plus per-currency MRR/ARR from recurring terms. Reports require `membership`;
MRR also requires `VIEW_FINANCE`. Months follow the makerspace timezone. MRR is a plan projection,
uses current prices and waiver state, and excludes custom-day plans. It is separate from collected revenue.
Scheduled reports may require non-empty rows or a numeric metric threshold before generating a file.
Role slugs and action selectors resolve eligible staff at send time, including report authority and
notification opt-out. Currency thresholds must choose a currency when the report contains several.
Delivery remains a private, expiring download link. Purging reports deletes report saved views,
schedules and delivery files; other saved staff-list views remain. Portable imports reset saved-view
state/sharing and drop schedules, so neither restores source disclosure rules.

### analytics

Per-space Metabase analytics (release 2, lane L25; owner decision #163B). **Off by default**; no
module requires it and it requires none. It adds:

- **A read-only database login per space.** The Space Manager (or the superadmin) creates, rotates
  and revokes it under Analytics in the staff console; the password is shown once and kept only as
  ciphertext. The login reads the curated views in the `spaceworks_analytics` schema and nothing
  else. It is a member of L8's `spaceworks_rls_fixed` group and pinned to its space by a
  `tenant_rls.FixedRoleScope` row, so row-level security limits it to that space whatever settings
  it sends. It owns nothing and holds no `BYPASSRLS`.
- **Curated, versioned views** over inventory and loans, machines and jobs, bookings, events,
  tickets and orders, membership, the payments ledger (amounts only) and To-Buy. They carry no
  secrets, tokens, evidence keys, contact fields or free text; member names and emails appear only
  in `members`, and only when the space turns **Show member details** on. The list, columns and
  version are in [Analytics views](analytics-views.md).
- **Embedded dashboards.** The Space Manager pastes the Metabase site URL and its embedding secret
  (encrypted at rest) and lists the dashboards to show. Staff holding `view_analytics` (the Space
  Manager always does) open them inside the console through a signed embed URL that expires after
  ten minutes; the secret never reaches the browser.
- **One platform-wide Metabase** (superadmin only, not per space): its own login over the
  `spaceworks_analytics_platform` schema, which sees every space and never member details.

Every create, rotate, revoke and view of the credentials, every connection change and every
dashboard opened is audited (`analytics.*`).

**Without it:** the Analytics tab and every per-space analytics route answer 404, and the space's
views return no rows. The connection, its dashboards list and the login are kept, so switching it on
again restores them. Revoke the login to remove it from the database.

**Hosting:** creating logins needs a database owner that can create roles (the bundled Postgres
can). Where it cannot (some managed or free-tier databases), the console says analytics is not
available on this hosting; nothing else is affected. Purging the module, or the space, drops its
login.

## Payments

### payments

[Read the payments module reference](MODULES-PLATFORM.md#payments).
Native Stripe/Razorpay flows and both providers' settings/webhook provisioning:
[mobile integration operator guide](mobile-integration.md#payments-stripe-and-razorpay).
The module gates the online rail; core charge history, receipts and desk settlement remain available.
Refund cases and per-area (and per-membership-plan) refund policies are core ledger too (no module or feature key): staff decide
every refund in the **Refunds** queue, and without the rail an online-paid case can only be declined.
See [refund cases in payment billing](payment-billing.md#refund-cases-and-policies).

### Donations and sponsors (`finance.*`, release 2)

No module key (#97): four parentless capabilities on the core ledger, each off by default.
`finance.donations` adds a public donation page per space (optional campaigns and funds with a goal
and window), one-off gifts from anyone (signed in, or a guest confirmed by an emailed code), gifts
staff record at the desk, and receipts; `finance.recurring_donations` adds pledges that raise one
charge each month, quarter or year (no card is stored); `finance.tax_exempt_receipts` adds India 80G
receipts (the donor PAN is always encrypted); `finance.sponsors` adds sponsors, tiers, perk
checklists, sponsorship charges and an opt-in sponsor wall on Pages and the event page.
`payments.donations` puts the online rail behind gifts and sponsor money. Every gift is income in
the finance ledger's `donations` area; returning one is a staff-approved refund case. Turning a
switch off hides its screens and routes and stops its jobs; gifts, pledges and sponsors are kept, and
their charges stay in the ledger (they are never purged). Finance staff get reports for each switch:
campaign progress, pledges (active, missed, paused, cancelled) and sponsor perks due or fulfilled, plus
the `finance-donations` money area; none of them shows a donor's name, contact or PAN. See
[donations and sponsors](payment-billing.md#donations-and-sponsors).

## Mobile apps

### mobile

[Read the mobile module reference](MODULES-PLATFORM.md#mobile).
Configure branded app registrations, identity, associations and readiness with the
[mobile integration operator guide](mobile-integration.md). A native staff grant is a step-up on
a person holding a staff role in its fixed tenant, with MFA and attestation. Phone/social/OIDC
native login is member-only; platform grants are forbidden. Push uses envelope-owned device
children independently of inbox creation. Delivery policy admits source-tied account-only
owners, while native selection/new registration still require local membership. Logout-all
is account-wide; self-deletion/restore are member-only. Core messaging consent is independent
of this module; SMS/WhatsApp each have their own opt-in key.

## Backup

### backup

**Retired** in P1b: not a module any more; per-space backup and restore are a platform duty with no
switch. [What changed](MODULES-PLATFORM.md#backup-retired).

## Connected devices

### devices

[Read the devices module reference](MODULES-PLATFORM.md#devices).


## Shop

### shop

Release 2 (L22; #128 C-7, #129, #135-#137). **Off by default.** Each makerspace may run its own shop:
its own catalogue, stock, prices, receipts and finance records; nothing is shared between spaces and the
superadmin sees every space's shop. It sells consumables and kits (stock goes down on sale), merch with
sizes and variants, online from a public shop page for pickup, and at the front desk. The shop is its own
top-level module, an owner exception to #97 (#135 Q-S1).

- **What it adds:** the staff **Shop** tab (catalogue, stock, orders, the front-desk POS, cash-up, shop
  reports and settings), the public page `/m/<slug>/shop` with `shop.online`, "My shop orders" in the
  member area, a `shop` section for Pages, and the built-in **Shop Manager** role (`manage_shop`,
  `sell_shop`, `view_shop`; #137). Every sale is one `Payment` (subject `shop_order`, finance domain
  `shop`), so it is in the ledger, the income-versus-spending report and the shop reports.
- **Without it:** no shop route answers (404 `shop_closed`), no shop job runs and nothing is shown. Rows
  are kept; turning it back on restores everything (#95, #128 C-8).
- **Its switches** (every shop feature is optional, #135): `shop.online` (public page and online
  orders), `shop.guest_checkout` (name, email and an emailed code), `shop.holds` (15 minutes online,
  48 hours for pay-at-desk; default on), `shop.member_prices` (the space's member discounts, members-only
  items), `shop.tax` (a tax rate and HSN code per product, prices tax-inclusive; needs `billing.tax`),
  `shop.returns` (returns window, restock or write-off, a refund case), `shop.cash_up` (cash sessions with
  float, counted cash and variance; the two-person check applies to the cash-up), `shop.event_pickup`
  (collect at one of the space's events; needs `events`), `shop.order_limits` (a per-order limit),
  `shop.public_stock` (In stock / Low / Sold out, exact counts per product opt-in; default on),
  `shop.receipts` (receipt screen at 80 mm and A4 and by email; default on), `shop.reorder` (a To-Buy draft
  with `inventory.tobuy`, else a staff notice), `shop.bundles` (kits take their parts' stock),
  `shop.consumable_link` (a product draws on an inventory consumable). Money: `charges.shop`
  (standalone, default on: every sale is recorded) and `payments.shop` (the online card/UPI rail; needs the
  `payments` module; without it online orders are paid at the desk).
- **Purge:** a superadmin purge of the module removes the shop's catalogue, stock history and cash
  sessions; orders that carry a charge keep their `Payment` and documents, which are core ledger.

## Features: the level below a module

A feature is narrower than a whole module. The **Space Manager** switches it in the console, as does
the module's manager while holding that module's settings grant (#101, C-11). A feature is inert while
its parent module is off.

| Feature | Inside | Default | What it does | Without it |
|---|---|:--:|---|---|
| `billing.documents` | standalone core ledger (mail needs `email`) | ● | Issue numbered [receipt and credit-note PDFs](payment-documents.md), with issuer settings and accounting account mappings | New collections have no document; existing documents stay readable and documented charges still receive refund/correction documents |
| `ui.delight` | standalone (deployment flag `UI_DELIGHT_ENABLED`) | ● | Artwork, gentle motion and celebration moments across the app; reduced-motion preferences always apply | Plain screens with no decorative motion or artwork |
| `ui.easter_eggs` | standalone (deployment flag `UI_EASTER_EGGS_ENABLED`) | ● | Hidden playful moments; never on scanner, kiosk, check-in or payment screens | No easter eggs |
| `billing.reminders` | `notifications` (needs `email`) | | Email the payer about due and overdue charges using [core billing policy](payment-billing.md), including cash-only charges | No automatic payment reminders; debt and receipts stay visible |
| `charges.enabled` | — | ● | Master switch for recording money owed | The space charges for nothing: no debt is recorded in any area |
| `billing.tax` | standalone core ledger | | Single named tax or India GST (CGST/SGST/IGST, GSTIN check, place of supply, composition, exempt, LUT exports) frozen onto each new charge; tax invoices and credit notes numbered per financial year; GSTR-1 (JSON), GSTR-3B, tax summary and documents register reports ([payment billing](payment-billing.md#tax-and-gst)) | Every charge and document is exactly release 1: no tax, the single receipt series; settings and issued tax documents are kept |
| `billing.maker_checker` | standalone core ledger | | A second person with `record_payment` confirms every offline settlement (offline income only, #128 C-5) | One person records a cash/UPI/bank receipt and the charge is paid at once; an awaiting queue still drains |
| `billing.offline_claims` | standalone core ledger | | UPI QR for the exact amount and the payer's "I've paid" claim (UTR, once per reference) that staff confirm or reject | No QR and no claim form; existing claims stay readable |
| `billing.pay_links` | standalone core ledger | | Signed, expiring link that pays one account-less charge staff raised | No links; old links answer 404, the charges stay |
| `billing.disputes` | standalone core ledger | ● | Disputes list and staff notice for Stripe/Razorpay chargebacks (record only) | Disputes are still recorded, never shown |
| `billing.capture_flags` | standalone core ledger | ● | Late, duplicate and mismatched online captures are flagged and their receipt held for a staff decision | Release-1 behaviour: receipt on capture, audit-only late notices |
| `finance.ledger` | standalone core ledger | ● | Finance ledger screens and reports: income vs spending by month, area and machine type, expenses with receipts, opening balances, receipts-and-payments and subscription income per FY, per-event money ([finance ledger](payment-billing.md#finance-ledger)) | Screens and reports hidden; spending and receipts are still recorded (#128 C-15) |
| `charges.pricing` | standalone core ledger | ● | Price lists ([pricing](payment-billing.md#pricing-paid-and-free-everywhere)): free or paid per area with rates, caps, grace and billing increments; per-item prices (Inherit / Free / Custom); loan rental (per loan and per day, charged at checkout or at return), staff-set damage and lost charges; machine time AND material; hourly rooms; the member price preview. With nothing configured every new component is free | Only the release-1 price fields apply (deposit, late fee, room/event/plan prices, the machine-type price); the pricing screens and APIs are gone; rate cards and item prices are kept |
| `charges.discounts` | standalone core ledger (needs `charges.pricing`) | | Automatic member discounts for all members, a plan's members or one member; the single best one applies, then an event promo code | Everyone pays the list price; rules are kept |
| `charges.price_drop_refunds` | standalone core ledger | | When staff LOWER a price after people paid, the save previews the affected paid, not-yet-used items (upcoming bookings, tickets for events not yet held, prepaid machine jobs not yet started, membership terms not yet started) with the difference, and opens one refund case per item for the Space Manager or a finance admin (view_finance + record_payment) to approve ([price-drop refunds](payment-billing.md#price-drop-refunds)). Nothing refunds automatically; a price rise never charges more | No preview and no cases; a sold ticket's price stays frozen; cases already opened stay in the refund queue. The prepaid-job cases (cancelled before it starts, cheaper than its quote) do not depend on this switch |
| `inventory.consumables` | — (Inventory) | | Take-and-go items (screws, glue) logged as used, never lent; one staff list of item, machine and pool consumables; an automatic To-Buy draft at the reorder point | No consumable flag or list; flagged items stay unlendable |
| `inventory.vendors` | — (Inventory) | | Saved suppliers for To-Buy purchases and warranties | Supplier stays free text; vendors kept |
| `inventory.expected_back` | `public_inventory` | | Opted-in items show the earliest date a borrowed-out unit is due back (date only) | No date shown |
| `loans.reservations` | `request_workflow` | | Members choose when they will collect, up to N days ahead | No pickup time on requests |
| `loans.pickup_windows` | `request_workflow` | | An accepted request not collected in time expires and its items are free again | Accepted requests wait until handed over or cancelled |
| `loans.waitlist` | `request_workflow` (needs `notifications`) | | Queue for an item that is out; the next unit is held for the first in line for a set time | No waitlist; places kept |
| `loans.withdrawals` | `request_workflow` | | Members withdraw their own pending or accepted request | Only staff cancel requests |
| `machines.job_requests` | `machine_service` | ● | One "Request a job" form for every machine type that takes jobs, with files, the queue, ETA, quotes and pickup codes | No member submits a job; staff keep every job |
| `machines.job_quotes` | `machine_service` (needs `machines.job_requests`) | ● | Staff send a quote the member approves before the job queues, per machine type | No type asks for a quote |
| `machines.batch_start` | `machine_service` (needs `machines.job_requests`) | | Start several queued jobs on one machine run; time and material split across them | One job per machine run |
| `machines.pay_before_pickup` | `machine_service` (needs `machines.job_requests`) | | A finished job is handed over only once its charge is settled | Pickup never waits on payment |
| `machines.time_booking` | `machines` (needs `bookings`) | | Book a machine's time through bookings; types that require a booking can then only be used by the booker, and nobody starts a job while someone else holds it | Nothing is enforced; machine resources are kept |
| `machines.sessions` | `machines` | | Metered machine sessions: a checked-in, certified member scans the machine's QR, sees the rate, starts and stops; staff start, stop, correct and confirm; integrated machines report their own. Forgotten sessions stop at the type's maximum length, check-out or closing (flagged for a staff check). Bills the type's hourly rate, frozen at start, only while `charges.machines` is on. A purge deletes sessions and their corrections; charges and usage entries stay | Every session route answers 404 and no sweep runs; the manual-hours usage log is unchanged; sessions are kept |
| `loans.fee_waivers` | `request_workflow` | ● | Staff waive a loan's rental, late, damage or lost fees with a recorded reason; a fee already paid opens a refund case for approval; the deposit is never waived | No waive tool; waivers already written keep their loans free |
| `charges.machines` | `machines` (needs `machine_service`) | ● | Record a charge when a priced machine job completes | Machine jobs are free |
| `machines.integrations` | `machines` (needs `devices`, `machine_service`) | | **Foundation only; the integration is deferred (#76).** An enrolled printer device bound to a machine whose type has an enabled printer-agent binding may pull its approved jobs, report start/completion/failure through the machine-service workflow (failures held for staff) and send a bounded status snapshot. Superadmin `/control/` only; no console screen | Every integration route answers 404; bindings and snapshots are kept |
| `charges.bookings` | `bookings` | ● | Record a charge when a paid booking is confirmed | Bookings are free |
| `charges.events` | `events` | ● | Record a charge when a registration for a paid event is confirmed | Registration is free |
| `charges.membership` | `membership` | ● | Record dues and renewal charges | Dues are not recorded |
| `membership.auto_renew` | `membership` | | Open the next term after renewal settlement, with plan timing/retries/grace | Manual renewal terms remain available |
| `membership.lifecycle_mail` | `membership` | | Send renewal lifecycle mail to the member | No automated lifecycle mail |
| `membership.self_service` | `membership` | | Edit own contact fields, revoke sessions and cancel/leave | Staff manage membership changes |
| `membership.self_export` | `membership` | | Request a private personal ZIP/JSON export | No member export surface |
| `membership.plan_rules` | `membership` | | Financial-year, fixed-end and lifetime plans; separate renewal price; per-plan joining fee, rejoin rule, payment timing, join mode and form; late-renewal rule | Plans are rolling; plans already using these rules keep them, and changing them is refused |
| `membership.public_plans` | `membership` | | Plan cards and per-plan pages on the public site and page builder; applicants choose a listed plan | Join uses the default plan; listing fields kept |
| `membership.renewal_desk` | `membership` | | Renewal worklist, manual reminders (once per member per day) and extending a membership with a reason | Renewals run as configured; no desk |
| `membership.import` | `membership` | | CSV/Excel member import into pending memberships with emailed invitations, or record-only rows (#128 C-13) | No import; pending rows and invitations kept |
| `membership.import_sheets` | `membership` (needs `membership.import`) | | Member import from a Google Sheet shared as “anyone with the link can view”: the server fetches its CSV export once per preview/apply (read-only, no Google account, nothing kept) and runs the same preview, de-dup and invitations as a file (L13) | Upload only; a sheet request answers 404 |
| `membership.admission_tools` | `membership` | | Multi-use invite links (limit, expiry, revoke) and bulk approve/reject | One request at a time; links stop working and are kept |
| `membership.member_numbers` | `membership` | | Show the fixed member number and set its printed pattern | Numbers are still assigned, never shown |
| `membership.records` | `membership` | | State code, GSTIN and staff-only notes on the member record | Record fields hidden; kept |
| `membership.titles` | `membership` | | Display-only member titles; one primary title prints on the card | No titles shown; kept |
| `membership.consent` | `membership` | | Consent ledger: purposes, notice version, give and withdraw | No consent screens; the ledger is kept |
| `membership.erasure` | `membership` | | A member asks this space to anonymise their membership data; staff approve or reject | No erasure requests; existing ones kept |
| `membership.history` | `membership` | | The membership history timeline in words for staff and the member | No timeline; the term history is still written |
| `membership.register_tools` | `membership` | | Register filters by standing and the member-register CSV export (needs `reports`) | Plain roster only |
| `membership.insights` | `membership` | | Renewal, collection, bridge, breakdown, expiry-calendar, win-back and funnel reports (needs `reports`) | Those reports refuse |
| `membership.monthly_summary` | `membership` | | Monthly staff summary email as a scheduled-report preset, opt-out per person (needs `reports`) | The schedule is skipped while off; kept |
| `charges.loans` | `request_workflow` | ● | Record loan deposits, rental, late, damage and lost charges (amounts are set in Settings › Pricing › Lending, or the payment settings) | Lateness is recorded but never charged |
| `loans.enabled` | `staff_admin` | On | Public loan catalogue, borrow submission and staff loan consoles; disabling preserves core and data | Loan surfaces are hidden and new public borrowing is refused |
| `payments.enabled` | `payments` | ● | Master switch for all online payments | Every `payments.<area>` switch below is inert |
| `payments.machines` | `machines` | | Card rail for machine-job charges | Charges are still recorded and settled offline |
| `payments.bookings` | `bookings` | | Card rail for booking charges | Charges are still recorded and settled offline |
| `payments.events` | `events` | | Card rail for event charges | Charges are still recorded and settled offline |
| `payments.membership` | `membership` | | Card rail for dues | Dues are still recorded and settled offline |
| `payments.loans` | `payments` | | Card rail for loan deposits and late fees | Loan charges are still recorded and settled offline |
| `mobile.push` | `mobile` | ● | Native push notifications | Apps rely on in-app/inbox notifications |
| `mobile.watch_actions` | `mobile` | ● | Open, Mark seen (and Snooze with inbox snooze) buttons on phone and watch notifications; never money, evidence, approval or handover actions | Pushes still arrive, without buttons |
| `events.short_links` | `events` | | Short `/e/<code>` links with a daily visit count | Only the long event address; existing codes are kept and 404 |
| `events.online_delivery` | `events` | | Online/hybrid events and the confirmed-only join link | Every event reads as in person; join links are kept, never shown |
| `events.broadcast_templates` | `events` | `events.broadcasts` feature | 13 starter templates and the accent-band, photo-header and letter designs | Blank composer with the classic, bold and minimal designs; saved campaigns keep rendering |
| `events.approval_digest` | `events` | `notifications` | One 30-minute summary per organiser while approvals wait | No digest; approvals still show in the console |
| `events.anonymous_feedback` | `events` | ● | A feedback form may keep answers unlinked to people (certificates off) | Feedback is identified; a form already promised anonymous accepts nothing |
| `events.submission_integrity` | `events` | `events.hackathons` feature | Information chip when a repository has commits from before kickoff | No GitHub checks; existing flags kept |
| `events.mentor_chat_alerts` | `events` | `events.mentoring` feature | New help requests posted to chosen team chat rooms while mentors are on shift | Personal mentor notices only; room choices kept |
| `events.organization_sender` | `events` | `email` | Co-host organisation display name and Reply-To on event email | The space's own sender name; organisation settings kept |
| `notifications.inbox_snooze` | `notifications` | | Snooze and archive inbox messages | Every message shows; snooze and archive states kept |
| `notifications.web_push` | `notifications` | | Opt-in browser notifications (needs deployment VAPID keys) | No browser notifications; subscriptions kept |
| `notifications.escalation` | `notifications` | | One re-ping when an urgent staff notice is unseen for 30 minutes | No re-ping |
| `public_site.closed_notice` | standalone | | A Space Manager "closed for now" banner with an optional reopening date on the public page | No banner; the text is kept |
| `bookings.api_read` | `bookings` | | Minimal resource/reservation reads for operator-granted, tenant-bound HMAC server clients; arrivals need a separate scope | Integration reads refuse; booking and audit history stays |
| `bookings.passes` | `bookings` (needs `bookings.confirmations`) | | Answer-free pass designer, owner downloads and staff printing after active arrival | Pass routes refuse; stored layouts retained |
| `bookings.analytics` | `bookings` (needs `reports`) | | Resource calendar reservation occupancy with resource management AND tenant audit authority | Resource analytics refuses; existing tenant-wide utilisation is unchanged |
| `bookings.utilization_pdf` | `bookings` (needs `reports`, `bookings.analytics`) | | Audited resource PDF for a complete tenant-local period, requiring full tenant booking management AND audit | Resource PDF refuses; stored booking history stays |
| `bookings.exports` | `bookings` (needs `reports`) | | Tenant-local reservation contacts and custom-answer previews/CSV/XLSX, requiring resource management AND audit | New detail exports refuse; booking history stays |
| `events.organization_audience` | `events` | | Live organizer/venue-owner membership audience; no membership or account-registration prerequisite | Configuration and new admission refuse; existing owned tickets remain |
| `events.hackathons` | `events` | | Off-default programme applications, RSVP, teams and submissions; event config also required; integration pending | Programme actions refuse; history retained |
| `events.mentoring` | `events` | | Off-default Mentor Desk: mentor assignments, the help queue and office hours. A hackathon's teams ask as teams; on any other event a confirmed attendee drops in on their own (release 2, #128 C-36) | Mentor surfaces refuse; retained work/history remain |
| `events.mentor_rounds` | `events` | `events.mentoring` and `events.hackathons` features | Off-default leased mentor check-in rounds (they visit teams) | Round actions refuse; history retained |
| `events.volunteering` | `events` | | Off-default ordinary-event/hackathon postings/shifts/verified hours; integration pending | Volunteer actions refuse; retained hours/history remain |
| `events.project_gallery` | `events` | `events.hackathons` feature | Off-default frozen public project selections with live consent; integration pending | Public gallery/bytes refuse; private snapshots retained |
| `events.pairwise_judging` | `events` | `events.hackathons` feature | Off-default third judging mode: judges say which of two projects was better (CrowdBT ranking, at least three comparisons per project) | Pairwise routes 404, new pairwise rounds and their open/close/finalize refuse with 403; rounds, comparisons and cursors are kept and resume when switched back on |
| `events.certificate_designer` | `events` | | Immutable private certificate designs and server previews | Editing/previews refuse; existing issuance snapshots retained |
| `bookings.broadcasts` | `bookings` | `notifications`, `email` | Email upcoming resource bookers with live consent and booking checks | Compose, queue and delivery refuse; history retained |

| `events.website` | `events` | | Curated released pages with private assets and programmes | Enhanced routes and images disappear; core event details remain |
| `events.embed` | `events` | `events.website` feature | Exact-origin backend HTML cards | Embed route refuses |
| `events.broadcasts` | `events` | `notifications`, `email` | Email campaigns plus selected personal-channel notices, with live sender/recipient checks | Compose, queue and delivery refuse; history retained |
| `reports.event_pdf` | `reports` | `events` | Post-event PDF from the report registry | PDF refuses; event analytics/history retained |
| `reports.event_exports` | `reports` | `events` | Tenant-local registration/feedback previews and CSV/XLSX | Detail exports refuse; event history retained |
| `events.account_registration` | `events` | | Authenticated accounts can register for account-audience events | Events keep their members-only default |
| `events.invites` | `events` | | Invite-only registration with expiring, limited-use codes | Invite audience and invite administration are refused |
| `events.ticket_types` | `events` | | Public/member prices, sales windows and capacity per type | Flat event price applies |
| `events.promo_codes` | `events` + `events.ticket_types` | | Limited-use, expiring percentage or fixed-amount discounts | Promo redemption is refused |
| `events.offline_checkin` | `events` | | Expiring on-device roster plus event-scoped PIN check-in stations | Check-in needs a live connection and an authenticated staff actor |
| `machines.certifications` | `machines` | | Members need an unexpired certification per machine type to book a linked space or request work; overrides need machine-type authority and are audited | Training is tracked out of band; nothing gates a request or booking |
| `notifications.delegated_recipients` | `machines` (needs `notifications`, `machines.maintenance`) | | Machine-scoped maintainers manage maintenance alert recipients for their own machines | Only makerspace-level staff manage recipients |
| `maintenance.reminders` | `machines` (needs `notifications`, `machines.maintenance`) | | Notify scoped maintainers before and after maintenance is due | No maintenance reminders |
| `maintenance.meters` | `machines` (needs `machines.maintenance`) | | Usage-based schedules (hours, job counts) | Calendar schedules only |
| `maintenance.calendar_feed` | `machines` (needs `machines.maintenance`) | | Personal iCal feed of scoped maintenance | No feed |
| `inventory.maintenance_reminders` | — (needs `notifications`, `inventory.maintenance`) | ● | Due-soon and overdue notices for item and unit maintenance to the Inventory Manager | No item maintenance reminders; schedules stay |
| `bookings.room_maintenance_reminders` | `bookings` (needs `notifications`, `bookings.room_maintenance`) | ● | Due-soon and overdue notices for room maintenance to the Booking Manager | No room maintenance reminders; schedules stay |
| `inventory.self_checkout` | — | ● | Member self-checkout and staff direct handouts | Every handover goes through a staff-issued request |
| `inventory.contact_self_checkout` | — + `inventory.self_checkout` | | Without Member accounts, borrowers check tools out with name, phone and an emailed code (#91); evidence rules unchanged | Account-less checkout is refused; account-less returns always stay open |
| `presence.geofence` | — | ● | Required location check for self check-in | Self check-in refuses when disabled/unconfigured; authorized staff check-in remains available. Coordinates are not stored |
| `inventory.kiosk` | — | | Scanner and handover Stations at `/m/<slug>/kiosk/<station>`: a Station PIN opens the channel, and a signed-in staff operator lease attributes every online handover to a real person | No Station sessions, operator leases, work packages or kiosk commands; the public desk at `/kiosk/<slug>` is unaffected |
| `membership.id_programmes` | `membership` | | Organisation ID programmes hosted by this space: a join page, CSV import, approvals, numbered cards (`PREFIX-YYYY-0001`), a card design and the public check page | Programme pages and routes answer 404; programmes, cards and designs are kept |
| `membership.id_programmes_import_sheets` | `membership` (needs `membership.id_programmes`) | | ID-programme import from a public Google Sheet link, fetched once per preview/commit and parsed exactly like a CSV; covers event and programme member IDs (L13) | CSV only; a sheet request answers 404 |
| `membership.wallet_passes` | `membership` | | Apple and Google Wallet passes for member and programme cards, updated when the card changes; shown only once the platform pass credentials are set | No wallet buttons; issued passes stop updating |
| `events.id_cards` | `events` | | An ID card for every confirmed registrant, designed and published by the event's organisers (no approval by default), valid until the day after the event; the door scan identifies the card | No event cards; issued cards and designs are kept |
| `events.ticket_designs` | `events` | | Design tickets per event and ticket type; one check-in QR; the PDF can go with the confirmation email | Tickets use no custom design |
| `events.wallet_passes` | `events` (needs `events.id_cards`) | | Wallet passes for event ID cards | No wallet buttons on event cards |
| `events.orders` | `events` (needs `events.ticket_types`) | | One order buys several tickets (tiers that open on sell-out or end, pay-what-you-want with a minimum, group tickets, hidden tickets behind access codes, per-order limits, a booking fee); one `Payment` per order; every seat becomes its attendee's own registration once they sign in and claim it | The order shop and order routes answer 400/404; single registration is unchanged; orders, seats and their money are kept |
| `events.seat_holds` | `events` (needs `events.orders`) | | A checkout holds its seats for 30 minutes and releases them on expiry or failure | Seats are taken only when payment lands; a paid order with no room left opens a staff-approved refund |
| `events.addons` | `events` (needs `events.orders`) | | Kit, lunch, T-shirts with sizes and session seats sold with tickets, with event-local stock (never hardware inventory) | Add-ons are hidden and refused; sold lines are kept |
| `events.series_passes` | `events` (needs `events.orders`) | | One pass for every future occurrence of a series; a cancelled occurrence opens the organiser's partial amount as a refund case | Pass routes answer 400; issued passes keep their registrations |
| `events.transfers` | `events` (needs `events.orders`) | | Attendees hand a ticket to another account (credential rotated, card re-issued) or change ticket type (pay the difference, or a refund case for it), when the organiser allows | Transfers and type changes are refused |
| `events.desk_collect` | `events` | | Check-in staff record a pending ticket payment at the desk (receipt) or open a pay-now checkout | Settlement stays in the payments console |
| `events.refund_override` | `events` | | An event's own refund policy, shown before payment; after the first sale it may only become more generous | The space's events refund policy applies |
| `finance.donations` | standalone core ledger | | The donation page, campaigns and funds, one-off gifts (signed in or a guest with an emailed code), desk gifts and receipts; every gift is `donations` income in the ledger | Page, giving and staff screens answer 404; gifts and their charges are kept |
| `finance.recurring_donations` | standalone core ledger (needs `finance.donations`) | | Pledges that raise one charge per month, quarter or year; the giver pays each like any charge, no card stored; missed periods are never back-charged | No new pledges and no period charges; pledges are kept |
| `finance.tax_exempt_receipts` | standalone core ledger (needs `finance.donations`) | | India 80G receipts with the space's registration number and validity; the donor's PAN is asked only for an 80G receipt and is always stored encrypted | No 80G option; frozen receipts are kept |
| `finance.sponsors` | standalone core ledger | | Sponsors with tiers, perk checklists (who ticked, when), sponsorship charges and the opt-in sponsor wall (Pages section and event page) | Sponsor screens, wall and perk reminders are gone; rows are kept |
| `payments.donations` | `payments` (needs `finance.donations`) | | Gifts and sponsor money can be paid online | Gifts are settled offline with a receipt |
| `bookings.calendar_feed` | `bookings` | ● | A member's private calendar link for their own bookings | The link answers 404; links are kept and work again when turned back on |
| `events.calendar_feed` | `events` | ● | A member's private calendar link for their own event registrations | The link answers 404; links are kept |
| `events.shifts_feed` | `events` | | A person's private calendar link for their approved volunteer and mentor shifts | No shift link |
| `calendar.combined_feed` | standalone | | One private link per person with their bookings, registrations and shifts in this space | No combined link |
| `events.public_feed` | `events` | | A public calendar of the space's listed, published events | No public calendar |
| `events.venue_fees` | `events` | | The space charges an outside organiser for hosting: flat and/or per hour from the space default, a room override or the event's own amount, charged once on publish | No venue fee is configured or charged; raised charges are kept |
| `events.applications` | `events` | | Applications for any one-off event: a form, review, offer, RSVP and waitlist, like hackathon admission without teams; paid places are charged after confirming | Application routes answer 404 on events without hackathons; applications are kept |
| `events.application_stages` | `events` (needs `events.applications`) | | Review stages: a panel per stage, at most ten criteria scored 1 to 5, blind review, 1 to 20 reviews per application, a seeded BALANCED or RANDOM assignment and an "advance" decision; an optional stage-advanced email per event | One review round per application; stages, panels and reviews are kept |
| `events.attendance_confirmation` | `events` | | Staff ask registered people "Are you still coming?" (12 hours apart, never automatic); replies show in the guest list, at the desk and in the export; per event, a No can free the place | No attendance emails or reply page; replies are kept |
| `events.crew` | `events` | | The event crew: a reviewed sign-up link (dietary needs can be filled from Saved details when the member asks), free crew places outside capacity, a catering count, an opt-in public crew section (per event, and as a Crew section on the event's page), and a crew chip (Mentor or the crew role) on event ID cards, tickets and badges; crew gain no staff access | No crew screens or sign-up; no chip; the page section renders nothing; crew rows and places are kept |
| `events.crew_claims` | `events` (needs `events.crew` and `event_reimbursements`) | | Crew members claim expenses through event reimbursements; money out goes through the expense ledger | Crew expense requests are refused |
| `events.checkin_lists` | `events` | | Swag, meal and workshop lists beside entry check-in, optionally only after entry or only for buyers of an add-on (counted by quantity); online only | No lists; scans are kept |
| `events.finalists` | `events` (needs `events.hackathons`) | | Advance the top N (ties kept) or hand-picked projects of a finalized round into a draft round, then publish them separately: a finalists block on the public results page, an optional finalists email and finalist certificates; results and prizes come from the final round | Finalist routes answer 404; advances and announcements are kept |
| `events.prize_payouts` | `events` (needs `events.hackathons`) | | A prize amount per winner and payouts recorded by hand by RECORD_PAYMENT holders or the Event Manager, each one an expense in the finance ledger; corrections are reversal rows. Never paid automatically | Payout routes answer 404; payouts and ledger rows are kept |
| `events.entry_fees` | `events` (needs `events.hackathons`) | | An entry fee per project; the project stays a draft until it is paid or waived; a disqualification can open a refund case (per event) | Nothing is charged or held; raised charges are kept |
| `events.paid_teams` | `events` (needs `events.hackathons`) | | One fixed price per team, charged once on the leader after the team is confirmed; the team is held until paid; a rejected team opens a refund case for the leader's payment | Nothing is charged or held; raised charges are kept |
| `events.prize_claims` | `events` (needs `events.prize_payouts`) | | Winning teams split a cash prize between members (the leader proposes, each member confirms, or staff record it); each winner gives where to be paid from the space's accepted payee templates and, when the space records prize tax, a PAN. Details are encrypted and only ever shown masked; finance reveals them to pay (audited). An optional claim window, after which staff may forfeit an unpaid prize. "My prizes" for members. Staff still record every payout by hand | Split, claim and My prizes routes answer 404; shares and claims are kept |
| `events.deposits` | `events` (needs `events.hackathons`) | | An optional refundable commitment deposit per hackathon, charged when a place is confirmed. After the event staff approve one settlement batch: people who came (and submitted, if the event requires it) get a refund case staff still approve; no-shows keep the charge | Nothing is charged; raised deposits and their cases are kept |
| `events.accepted_addons` | `events` | | On events that review registrations, people already confirmed can buy add-ons (a T-shirt, meals, a hardware kit) without buying another seat | Add-on-only orders are refused on approval events; placed orders are kept |
| `events.saved_views` | `events` | | Filtered staff lists of guests, teams, submissions, results and judging progress, with saved views and a CSV export of exactly the filtered rows | List and export routes answer 404; saved views are kept |
| `events.gallery_search` | `events` (needs `events.project_gallery`) | on | Search, sort (newest, A to Z, award winners first) and an award-winners filter on the public gallery, with award badges once results are published | The plain gallery list; search parameters answer 404 |
| `events.peoples_choice` | `events` (needs `events.project_gallery`) | | An optional People's choice award per event, beside judging (never instead of it): signed-in members (or, per event, only checked-in attendees) vote once for a public gallery project and may change it until voting closes; never for their own team; staff see the count and who voted (never whose vote went where), void abusive ballots with a reason, and publish the result once; the award shows on the gallery, the results page and the event page, and a prize it carries is paid like any prize | People's choice routes answer 404 and the gallery shows no vote buttons; settings, ballots and published results are kept |
| `platform.help_centre` | — | ● | The [in-app help centre](#the-help-centre-platformhelp_centre): role-gated guide articles and a "Help" link beside each staff console screen | No Help links in the console; the space's `/help` routes answer "page not found". Nothing is stored, so nothing is lost |

The `payments.<area>` switches are **off by default and stay inert until credentials resolve** —
turning one on cannot start charging anyone by itself. They only put a card rail behind a debt the
matching `charges.<area>` switch records: with `charges.<area>` off, turning `payments.<area>` on records
nothing and offers nothing (the two are deliberately independent switches, the A6 rule). `inventory.self_checkout` and `presence.geofence`
belong to no module: they are standalone capabilities that apply whenever you enable them.

## The help centre (`platform.help_centre`)

A standalone feature, on by default. The guide lives at `/help` (and `/m/<slug>/help` on the central
origin); every staff console screen carries a "Help" link that opens the matching article in a new tab.

- **Who sees what.** Everyone reads the member and organisation sections. Staff sections follow the
  reader's actions in any space (Inventory Manager, Machine Manager, Booking Manager, Event Manager,
  finance, Technician, Shop Manager, handover); a Space Manager sees every staff section; the platform
  superadmin also sees the superadmin and host-operator sections. Search only covers the articles the
  reader can see. The gating chooses what is relevant; it is not a security boundary, so articles never
  hold secrets or anything a member must not read.
- **Content.** Articles are content files under `frontend/src/help-content/<locale>/<section>/`, one
  Markdown file each, so translations add a locale folder rather than code (L9). Screenshots are
  placeholders until the release phase takes them from the `seed_showcase` space.
- **Without it.** The console shows no Help links and the space's help routes answer "page not found".
  The platform-wide `/help` on the central origin belongs to no space and stays available.

## The public stats page (not a module)

`/m/<slug>/stats` (and the full-screen `/m/<slug>/stats/tv`) is a public-site setting, not a
module or capability (#97, #170): the Space Manager sets it up in **Settings › Public stats** —
page on/off, which sections and in what order, one fixed period (this month, this year, all time
or this financial year), up to four headline numbers, and TV mode with its refresh (default 60
seconds, at least 30). Only the Space Manager and the superadmin change it, through the settings
authority (module `public_site`, audited as `settings.changed`).

Each section also follows its module; a module that is off hides its section and keeps its data:

| Section | Needs | Shows |
|---|---|---|
| Events | `events` | upcoming listed public events (cards only), events held and checked-in attendees in the period |
| Machines | `machines` | machine hours all time and in the period (public, active machines) |
| Printing | `machine_service` + `printing` | the printer kernel figures, print hours and prints completed in the period |
| Lending & inventory | `public_inventory` and the catalogue switch | the public library, current loans, loans in the period |
| Community | `membership`, `bookings`, `presence` (each count on its own) | active and new members, bookings, check-ins |

Counts never carry a name and any count below 3 shows as "fewer than 3". New spaces start with
machines, printing and lending on, events and community off, and the page itself off. The page
builder's own "Public stats" section (Settings › Public page) is separate and unchanged.

## The platform overview (superadmin, not a module)

**Platform dashboard › Platform overview** in the web superadmin console (#183A) combines every
live space's numbers: a total for each figure, always shown beside the per-space table it adds up.
It is not a module and has no switch; it is platform-only (`GET /admin/platform/overview`, CSV at
`/overview/export`). Periods are UTC: this month, this year, all time or a custom range. Archived,
not-serving (importing/aborted) and directory-hidden spaces are left out unless the superadmin ticks
**Include archived, not-serving and directory-hidden spaces**; a directory-hidden space shown that
way is still live, so its name still links into the console.

Each block follows its own switch, space by space: a space with the switch off shows "Off" in the
table and adds nothing to the total. A block whose switch is off in every space is hidden, and the
Modules section names it. Each block says "Off in N spaces".

| Block | Needs | Shows |
|---|---|---|
| People | always | active members, new sign-ups, active staff by role; platform-wide person accounts (not split by space, since one person can belong to several) |
| Lending | `loans.enabled` | catalogue items, loans issued, out now, overdue now, returned, requests awaiting review |
| Machines | `machines` | active machines, jobs by status, sessions, session hours, utilisation (session hours over machines x period hours; none for all time) |
| Events | `events` | events held, upcoming, registrations, people checked in, hackathon submissions |
| Bookings | `bookings` | bookings, booked hours, no-shows, cancellations, awaiting approval |
| Membership | `membership` | active memberships, new, renewals, lapsed (expired and not renewed) |
| Money | `charges.enabled`, `payments`, `shop` or `finance.donations` | per currency: charges raised, charged, collected, still owed, refunded, waived, expenses, donations and sponsorship, shop sales |
| Operations | always | storage used, emails waiting/failed, failed notifications, space backups and restore drills; platform-wide emails, whole-platform backups, network blocks and unusual sign-in alerts |

Counts and money only: no member name, email or contact ever leaves the overview. Money is never
added across currencies. Each space's name links to that space in the console (`?space=<id>`).
Exporting the CSV writes a `platform.overview_exported` audit row.

## Editions

[Read about editions](MODULES-LIFECYCLE.md#editions).

## Install profiles

[Read about install profiles](MODULES-LIFECYCLE.md#install-profiles).

## Deleting a module's data

[Read about deleting a module's data](MODULES-LIFECYCLE.md#deleting-a-modules-data).

## Removing a module from the build entirely

[Read about removing a module from the build entirely](MODULES-LIFECYCLE.md#removing-a-module-from-the-build-entirely).

Event website content includes speaker profiles and private photos, tiered sponsors and logos,
venue and room information, highlights, a tagline, accent colour and ordered section switches.
Turning a website section off also hides its direct public detail and image access unless
another enabled section uses the image. Content editing requires event `edit_details`;
programme edits and live track delays require `publish_schedule`. These additions use the
existing `events.website` feature; embedding still additionally requires `events.embed`.

### event_reimbursements

Opt-in, off by default, and dependent only on `events`. Adds support requests,
finite budget pools, awards and post-event expense claims to ordinary events and
hackathons. Staged forms belong to Events and work without this module.

Payouts record payments already made by a human; this module never transfers money.
Core Payments retains obligations, encrypted payee revisions, decision evidence and
append-only payout corrections independently of Events, this module and the online
payment rail. Recording/amending requires both `view_finance` and the separate
`record_reimbursement_payout` action plus recent session reauthentication. Only the
Space Manager built-in gains that action; `record_payment` grants no payout access.
Archive pauses finance access until unarchive. Uninstall preserves all rows.
Destructive module purge must refuse unfinished awards/claims or missing core
evidence/attachment closure, then preserve the core ledger. Whole-tenant purge
keeps its existing explicit full-graph behavior. Payee and decision-summary fields
require the tenant key broker even with optional PII encryption disabled.

A support request can be sent with the registration or hackathon application (it is
saved in the same transaction), or later from the member's event page. Sending one
while this module is off is refused rather than silently dropped. Award-acceptance and
claim-deadline reminders, and the core payee-details reminder, run through the shared
reminder sweeper. Check-in and attendance corrections feed claim eligibility. Receipt
retention, payee purge timing and attachment budgets are deployment settings
(`EVENT_REIMBURSEMENT_*`). Archiving shows the count of unpaid event payouts and warns
that settlement stops until the makerspace is restored. `purge_module_data --preflight`
prints the blockers and preserved ledger counts without deleting anything; the same
preflight always runs before a real purge, and `--yes` skips only the prompt.
Moving a space to another deployment carries every request, award, claim, decision,
payout, payee record and receipt (payee bank details stay encrypted throughout); the
imported programme arrives paused until finance reconciles it on the new deployment.
