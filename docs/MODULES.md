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
certification gating. Staff MFA is a separate question.
The per-person accounts module (self sign-up, password/Google/Apple/GitHub/phone sign-in and the member
area) is always installed by setup; platform login-method switches and the provider selection still
govern sign-in availability. Membership adds plans, vouching, renewals and the mobile app.

| Area | Modules | Features |
| --- | --- | --- |
| Inventory & lending | `public_inventory`, `request_workflow`, `staff_admin`, `scanner`, `evidence_uploads`, `qr_management` (core); `guest_handover`, `asset_units`, `containers`, `bulk_import`, `stock_transfers`, `qr_print_batches`, `stocktake`, `devices` | `loans.enabled`, `loans.limits`, `loans.renewals`, `loans.kit_checklist`, `inventory.notify_when_back`, `inventory.tobuy`, `inventory.warranty`, `inventory.self_checkout`, `inventory.contact_self_checkout`, `inventory.kiosk`, `stocktake.discipline`, `packs.import`, `charges.loans`; `payments.loans` with Online payments |
| Machines | `machines`, `machine_service`, `printing` | `machines.maintenance`, `machines.tobuy`, `machines.warranty`, `machines.certifications`, `machines.certification_reminders`, `machines.public_detail`, `machines.material_catalogue`, `machines.structured_intake`, `maintenance.reminders`, `maintenance.meters`, `maintenance.calendar_feed`, `charges.machines`, `notifications.delegated_recipients`; `payments.machines` with Online payments |
| Events | `events` | `events.api_read`, `events.certificate_designer`, `events.website`, `events.embed`, `events.short_links`, `events.online_delivery`; `events.broadcasts` with Notifications and Email; `events.organization_audience`, `events.offline_checkin`, `events.invites`, `events.account_registration`, `events.ticket_types`, `events.promo_codes`, `charges.events`; `payments.events` with Online payments |
| Bookings | `bookings` | `bookings.recurring`, `bookings.staff_grants`, `bookings.clone`, `bookings.staff_tools`, `bookings.confirmations`, `bookings.checkin`, `bookings.passes`, `bookings.api_read`, `bookings.website`, `bookings.embed`, `charges.bookings`; `bookings.broadcasts` with Notifications and Email; `bookings.analytics`, `bookings.utilization_pdf`, `bookings.exports` with Reports; `payments.bookings` with Online payments |
| Membership | `membership`, `mobile` | `membership.auto_renew`, `membership.lifecycle_mail`, `membership.self_service`, `membership.self_export`, `membership.vouching`, `membership.application_form`, `membership.broadcasts`, `mobile.push`, `charges.membership`; `payments.membership` with Online payments |
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
feature, keeping existing settings and staff MFA unchanged. Newly enabled areas get defaults;
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
| **Module** | Space Manager or superadmin (console or CLI) | A whole capability. Installing adds its surfaces; uninstalling hides them and **keeps every row**. On the managed platform a module with a fair-use limit is installed by the superadmin only (#128 C-10). |
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

The registry contains 35 keys (34 in the main catalogue plus presence): six core,
member accounts enabled by default, and 28 opt-in. `maintenance` and `procurement`
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
**Events**: [events](#events) — **Bookings**: [bookings](#bookings) —
**Membership**: [membership](#membership) · [presence](#presence)
**Notifications**: [notifications](#notifications) · [email](#email) · [sms](#sms) · [whatsapp](#whatsapp) · [telegram](#telegram) ·
[slack](#slack) · [mattermost](#mattermost) · [discord](#discord) · [webhook](#webhook) — **Reports**: [reports](#reports) —
**Payments**: [payments](#payments) — **Accounts**: [member_accounts](#member_accounts) —
**Mobile apps**: [mobile](#mobile) · **Connected devices**: [devices](#devices)

---

## Inventory

### public_inventory

[Read the public_inventory module reference](MODULES-INVENTORY.md#public_inventory).

### request_workflow

[Read the request_workflow module reference](MODULES-INVENTORY.md#request_workflow).

### staff_admin

[Read the staff_admin module reference](MODULES-INVENTORY.md#staff_admin).

Staff use separate, tenant-bound accounts created by a Space Manager or permitted superadmin.
Password sign-in and admin-issued reset remain available without Member accounts, Membership,
Email, staff invitations or MFA. Modules never turn a member into built-in staff.

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
| `machines.maintenance` | `machines` | | Machine maintenance schedules, logs, documents, overdue list, calendar feed, reminders and the dashboard/report sections |
| `machines.tobuy` | `machines` | | To-Buy rows for machine consumables (the `printing` stream) and automatic filament low-stock drafts |
| `machines.warranty` | `machines` | | Warranty records and documents on machines |
| `inventory.tobuy` | — (Inventory) | | To-Buy rows for inventory items (the `hardware` stream), reorder drafts and, later, the shop |
| `inventory.warranty` | — (Inventory) | | Warranty records and documents on inventory assets |
| `machines.repairs`, `machines.issue_reporting` | `machines` | | Reserved for repairs and issue reporting (L16); no effect yet |
| `inventory.maintenance`, `inventory.repairs`, `inventory.issue_reporting` | — (Inventory) | | Reserved (L12/L16); no effect yet |
| `bookings.room_maintenance`, `bookings.room_repairs`, `bookings.issue_reporting` | `bookings` | | Reserved (L16); no effect yet |

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
  grant (see [Settings authority](INVARIANTS.md#settings-authority)).


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

**Programme checkpoint (2026-10-18, `f1ef7736`): keep the new features off.** Hackathons
are features inside Events, not a separate module. Five declared switches default off:
`events.hackathons`, `events.mentoring` (requires hackathons), `events.mentor_rounds`
(requires mentoring), `events.volunteering`, and `events.project_gallery` (requires
hackathons). Release 2 adds one more, off and requiring hackathons: `events.pairwise_judging` (a third
judging mode). KiCad files stay download-only (owner, 2026-10-29). Each hackathon also needs its disabled-by-default event config enabled.
Volunteering can serve ordinary events. Schema, routes and generated API exist; live
provider installation and acceptance remain incomplete. See the [runbooks](events/README.md)
and [exact integration closure ledger](events/integration-status.md).

The current `setup_areas.features_for()` selects every child of a chosen area, including
these five when Events is selected. That setup path still needs an explicit independent
opt-in/exclusion before programme acceptance; do not infer safe installation from the
registry's false defaults alone.

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
core money ledger, global account vault and foreign profile bytes. **Durable multipart/
version cleanup receipts and storage reconciliation still need integration**; collecting
keys is not proof that purge removed bytes. Imported public/consent/grant/credential state
is inert until fresh target-side authorization; imported storage allowance is zero until
target accounting is installed.

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

This controls the community account ecosystem. Staff/platform password doors and staff
admin-issued recovery are independent; member self-service recovery never resets staff/platform.

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
separates notification usage from OTP counts; [measurement notes](report-builders-messaging.md).

### whatsapp

Default off and personal-only, with canonical Twilio/Meta providers. The combined registry
contains this key, removing the former Meta missing-module readiness blocker. Existing operational
installations need explicit conversion preserving enablement and opt-outs; platform senders stay off
until the operator enables them.

[Read the WhatsApp module reference](MODULES-PLATFORM.md#whatsapp).
Provisioning and the shared sender correlation barrier: [messaging operator guide](messaging-channels.md).
With reports enabled, communications health includes scoped WhatsApp progress and
delivery/read rates plus a labelled current consent snapshot. Platform usage exposes
counts only; [measurement notes](report-builders-messaging.md).

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

## Payments

### payments

[Read the payments module reference](MODULES-PLATFORM.md#payments).
Native Stripe/Razorpay flows and both providers' settings/webhook provisioning:
[mobile integration operator guide](mobile-integration.md#payments-stripe-and-razorpay).
The module gates the online rail; core charge history, receipts and desk settlement remain available.
Refund cases and per-area (and per-membership-plan) refund policies are core ledger too (no module or feature key): staff decide
every refund in the **Refunds** queue, and without the rail an online-paid case can only be declined.
See [refund cases in payment billing](payment-billing.md#refund-cases-and-policies).

## Mobile apps

### mobile

[Read the mobile module reference](MODULES-PLATFORM.md#mobile).
Configure branded app registrations, identity, associations and readiness with the
[mobile integration operator guide](mobile-integration.md). Native staff require a separate
staff account, password/MFA/attestation and fixed-tenant local actions. Phone/social/OIDC
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
| `charges.machines` | `machines` (needs `machine_service`) | ● | Record a charge when a priced machine job completes | Machine jobs are free |
| `charges.bookings` | `bookings` | ● | Record a charge when a paid booking is confirmed | Bookings are free |
| `charges.events` | `events` | ● | Record a charge when a registration for a paid event is confirmed | Registration is free |
| `charges.membership` | `membership` | ● | Record dues and renewal charges | Dues are not recorded |
| `membership.auto_renew` | `membership` | | Open the next term after renewal settlement, with plan timing/retries/grace | Manual renewal terms remain available |
| `membership.lifecycle_mail` | `membership` | | Send renewal lifecycle mail to the member | No automated lifecycle mail |
| `membership.self_service` | `membership` | | Edit own contact fields, revoke sessions and cancel/leave | Staff manage membership changes |
| `membership.self_export` | `membership` | | Request a private personal ZIP/JSON export | No member export surface |
| `charges.loans` | `request_workflow` | ● | Record loan deposits and late fees (amounts are set in payment settings) | Lateness is recorded but never charged |
| `loans.enabled` | `staff_admin` | On | Public loan catalogue, borrow submission and staff loan consoles; disabling preserves core and data | Loan surfaces are hidden and new public borrowing is refused |
| `payments.enabled` | `payments` | ● | Master switch for all online payments | Every `payments.<area>` switch below is inert |
| `payments.machines` | `machines` | | Card rail for machine-job charges | Charges are still recorded and settled offline |
| `payments.bookings` | `bookings` | | Card rail for booking charges | Charges are still recorded and settled offline |
| `payments.events` | `events` | | Card rail for event charges | Charges are still recorded and settled offline |
| `payments.membership` | `membership` | | Card rail for dues | Dues are still recorded and settled offline |
| `payments.loans` | `payments` | | Card rail for loan deposits and late fees | Loan charges are still recorded and settled offline |
| `mobile.push` | `mobile` | ● | Native push notifications | Apps rely on in-app/inbox notifications |
| `events.short_links` | `events` | | Short `/e/<code>` links with a daily visit count | Only the long event address; existing codes are kept and 404 |
| `events.online_delivery` | `events` | | Online/hybrid events and the confirmed-only join link | Every event reads as in person; join links are kept, never shown |
| `public_site.closed_notice` | standalone | | A Space Manager "closed for now" banner with an optional reopening date on the public page | No banner; the text is kept |
| `bookings.api_read` | `bookings` | | Minimal resource/reservation reads for operator-granted, tenant-bound HMAC server clients; arrivals need a separate scope | Integration reads refuse; booking and audit history stays |
| `bookings.passes` | `bookings` (needs `bookings.confirmations`) | | Answer-free pass designer, owner downloads and staff printing after active arrival | Pass routes refuse; stored layouts retained |
| `bookings.analytics` | `bookings` (needs `reports`) | | Resource calendar reservation occupancy with resource management AND tenant audit authority | Resource analytics refuses; existing tenant-wide utilisation is unchanged |
| `bookings.utilization_pdf` | `bookings` (needs `reports`, `bookings.analytics`) | | Audited resource PDF for a complete tenant-local period, requiring full tenant booking management AND audit | Resource PDF refuses; stored booking history stays |
| `bookings.exports` | `bookings` (needs `reports`) | | Tenant-local reservation contacts and custom-answer previews/CSV/XLSX, requiring resource management AND audit | New detail exports refuse; booking history stays |
| `events.organization_audience` | `events` | | Live organizer/venue-owner membership audience; no membership or account-registration prerequisite | Configuration and new admission refuse; existing owned tickets remain |
| `events.hackathons` | `events` | | Off-default programme applications, RSVP, teams and submissions; event config also required; integration pending | Programme actions refuse; history retained |
| `events.mentoring` | `events` | `events.hackathons` feature | Off-default mentor assignments/help/office hours; integration pending | Mentor surfaces refuse; retained work/history remain |
| `events.mentor_rounds` | `events` | `events.mentoring` feature | Off-default leased mentor check-in rounds; integration pending | Round actions refuse; history retained |
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
| `inventory.self_checkout` | — | ● | Member self-checkout and staff direct handouts | Every handover goes through a staff-issued request |
| `inventory.contact_self_checkout` | — + `inventory.self_checkout` | | Without Member accounts, borrowers check tools out with name, phone and an emailed code (#91); evidence rules unchanged | Account-less checkout is refused; account-less returns always stay open |
| `presence.geofence` | — | ● | Required location check for self check-in | Self check-in refuses when disabled/unconfigured; authorized staff check-in remains available. Coordinates are not stored |
| `inventory.kiosk` | — | | Scanner and handover Stations at `/m/<slug>/kiosk/<station>`: a Station PIN opens the channel, and a signed-in staff operator lease attributes every online handover to a real person | No Station sessions, operator leases, work packages or kiosk commands; the public desk at `/kiosk/<slug>` is unaffected |

The `payments.<area>` switches are **off by default and stay inert until credentials resolve** —
turning one on cannot start charging anyone by itself. They only put a card rail behind a debt the
matching `charges.<area>` switch records: with `charges.<area>` off, turning `payments.<area>` on records
nothing and offers nothing (the two are deliberately independent switches, the A6 rule). `inventory.self_checkout` and `presence.geofence`
belong to no module: they are standalone capabilities that apply whenever you enable them.

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
