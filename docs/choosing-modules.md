# Choosing modules

A makerspace only carries the parts it uses. Space Works ships **35 modules**; **6 are core** and
always on (the public catalogue, request workflow, staff admin, evidence uploads, QR management and
the scanner). The rest are **opt-in**.

Core is not negotiable because the hardware-handover rules depend on it: issuing a tool requires a box
QR scan *and* a photo, so a machines-only workshop still carries the request/QR/evidence spine.

This page is the operator's overview: areas, the full module list, features, and how to install,
uninstall, purge or remove a module. Per-module detail — what each key is, what it puts on screen,
**what happens if you do not install it**, and what becomes of its data if you later purge it — is in
[**MODULES.md**](MODULES.md).

## Areas

You do not have to think in 35 switches. They are grouped into **areas**, which is what the console
shows you:

| Area | Covers |
|---|---|
| **Inventory** *(always on)* | The catalogue, request workflow, QR/evidence spine, asset units, containers, transfers, QR print batches, front-desk handover and purchasing |
| **Stocktake** | Scan-first stock counts and variance reporting |
| **Machines** | Machine registry, the service/print queue, maintenance and warranty |
| **Events** | Event scheduling and registrations — recurring series, approval and waitlists, QR check-in at the door, post-event feedback and attendance certificates, member calendar feeds, printable attendee badges, and cross-makerspace collaborative events |
| **Bookings** | Resource booking and public self-booking |
| **Membership** | Join requests, waivers, referrals, member activity, maker profiles, presence — and the member-facing identity ecosystem |
| **Notifications** | The in-app inbox and every outbound channel |
| **Reports** | Analytics, the report registry and CSV/XLSX exports |
| **Payments** | Taking money online, through Stripe or Razorpay |
| **Mobile apps** | Attested device sessions, native push and the in-app payment sheet |
| **Connected devices** | Printers and label printers enrolled with their own signing key |

### Choosing areas during setup

**Choose areas before confirmation.** Setup enables each area's modules and every satisfiable feature.
Setup first asks whether to enable every area (default no); yes still asks the normal follow-ups.
Inventory & lending, Machines and Reports default on; the other five areas default off. Core,
notifications, email and the per-person accounts module stay installed, as do charge tracking, receipt
documents, billing reminders, staff invitations and self-check-in geofence. Accounts supplies self
sign-up, password/social/phone sign-in and the member area; platform login-method/provider choices still
apply. Membership adds plans, vouching, renewals and the mobile app. Inventory off hides lending through
`loans.enabled` and retains all data. See [Areas used by setup](MODULES.md#areas-used-by-setup) for the
module/feature mapping.

Change areas later with installer menu 2/3 or `scripts/update.sh --modules-only`. The menu displays
on/partial/off: numbers toggle, `a` selects all and `n` selects none. It asks settings only for newly
enabled areas. Automation can select an exact set:

```bash
bash scripts/update.sh --modules-only --areas=inventory,machines --makerspace my-space --confirm-removals
```

The full set of update and module flags is in [Install and update](install-and-update.md#upgrades-and-module-changes).

## Install and uninstall one module

**Change it later.** Uninstalling clears the capability and hides the surfaces; **your data is always
retained** and reinstalling brings it back:

```bash
docker compose run --rm --no-deps backend --role management python manage.py list_modules
docker compose run --rm --no-deps backend --role management python manage.py install_module bookings
docker compose run --rm --no-deps backend --role management python manage.py uninstall_module bookings
```

Core modules cannot be uninstalled, nor can one another installed module depends on.

## Deleting a module's data

Uninstalling only hides. If you also want a module's rows *gone*, that is a separate, deliberate
second step — so that no single command can both hide and destroy:

```bash
docker compose run --rm --no-deps backend --role management python manage.py purge_module_data bookings --list
docker compose run --rm --no-deps backend --role management python manage.py purge_module_data bookings --makerspace my-space
```

- **The module must already be uninstalled.** Purging an installed module is refused.
- **Superadmin only**, and it asks you to type the makerspace slug back before proceeding.
- **It cannot be undone.** Uninstall is reversible; this is not.
- **Payment records are kept.** Switching a module off and deleting its rows is not a reason to
  destroy the record of money that really changed hands, so receipts stay visible and a pending
  charge stays payable and can still be marked paid or waived. Each charge keeps the description it
  was raised under, so it still reads sensibly once the booking or event behind it is gone. Deleting
  a whole makerspace is the exception — there, its payments go with it.
- Uploaded files are removed after the database work commits, and your storage quota is credited
  back only for objects the bucket confirmed it deleted — a failed delete credits nothing, so the
  counter can never drift below what you are actually storing.

A module absent from the list either owns no data of its own or cannot be purged separately, and
the command tells you which. `machines` is the notable second case: machine rows host warranty
records, consumables and service history, so purge `machine_service` first.

## Every module, by area

The full list, so you can see exactly what an area is turning on. **Core** is always present and
cannot be removed. **Default** means it is on when you install outside the guided installer.

| Area | Module | Core | Default | What it adds |
|---|---|:--:|:--:|---|
| **Inventory** | [`public_inventory`](MODULES.md#public_inventory) | ● | ● | The public catalogue |
| | [`request_workflow`](MODULES.md#request_workflow) | ● | ● | Borrow requests and the state machine |
| | [`staff_admin`](MODULES.md#staff_admin) | ● | ● | The staff console |
| | [`evidence_uploads`](MODULES.md#evidence_uploads) | ● | ● | Issue/return photos |
| | [`qr_management`](MODULES.md#qr_management) | ● | ● | QR codes for boxes, tools and assets |
| | [`scanner`](MODULES.md#scanner) | ● | ● | The camera scanner |
| | [`asset_units`](MODULES.md#asset_units) | | | Individually tracked units of a product |
| | [`containers`](MODULES.md#containers) | | | Boxes and storage containers |
| | [`bulk_import`](MODULES.md#bulk_import) | | | Spreadsheet import |
| | [`stock_transfers`](MODULES.md#stock_transfers) | | | Moving stock, including between makerspaces |
| | [`qr_print_batches`](MODULES.md#qr_print_batches) | | | Printable QR sheets and ZIP export |
| | [`guest_handover`](MODULES.md#guest_handover) | | | Front-desk direct handouts |
| | [`procurement`](MODULES.md#to-buy-was-procurement) | | | The "to buy" list |
| **Stocktake** | [`stocktake`](MODULES.md#stocktake) | | | Scan-first stock counts and variance |
| **Machines** | [`machines`](MODULES.md#machines) | | | The machine registry |
| | [`machine_service`](MODULES.md#machine_service) | | | The service/job queue |
| | [`printing`](MODULES.md#printing) | | | 3D printing on top of `machine_service` |
| | [`maintenance`](MODULES.md#maintenance-was-maintenance) | | | Scheduled and reactive maintenance |
| **Events** | [`events`](MODULES.md#events) | | | Scheduling, recurring series, registrations and waitlists, QR check-in, feedback and certificates, collaborative events |
| **Bookings** | [`bookings`](MODULES.md#bookings) | | | Resource booking and public self-booking |
| **Membership** | [`membership`](MODULES.md#membership) | | | Join requests, waivers, referrals, maker profiles |
| | [`member_accounts`](MODULES.md#member_accounts) | | | Member sign-up and member sign-in |
| | [`presence`](MODULES.md#presence) | | | Member/guest check-in and privacy-controlled TV display |
| **Notifications** | [`notifications`](MODULES.md#notifications) | | | The in-app inbox |
| | [`email`](MODULES.md#email) | | | Outbound email |
| | [`telegram`](MODULES.md#telegram) | | | Telegram room/verified personal alerts; private account linking |
| | [`slack`](MODULES.md#slack) | | | Slack alerts |
| | [`mattermost`](MODULES.md#mattermost) | | | Mattermost alerts |
| | [`discord`](MODULES.md#discord) | | | Discord alerts |
| | [`webhook`](MODULES.md#webhook) | | | Signed JSON webhooks to your own systems |
| **Reports** | [`reports`](MODULES.md#reports) | | | Analytics, the ledger and CSV/XLSX export |
| **Payments** | [`payments`](MODULES.md#payments) | | | Taking money online (Stripe or Razorpay) |
| **Mobile apps** | [`mobile`](MODULES.md#mobile) | | | Attested device sessions, native push, payment sheet |
| **Connected devices** | [`devices`](MODULES.md#devices) | | | Signed device enrollment, printer reports and label commands |

`mobile` requires `member_accounts`; `printing` requires `machine_service`. Installing one pulls in
what it needs. `membership` deliberately does **not** require `member_accounts` — identity can come
from an external identity provider or a staff-created walk-in record instead (see
[Sign-in, identity and borrowing](sign-in-and-borrowing.md)).

## Features: the second level

Some capabilities are narrower than a whole module, so they are **features**. A feature with a parent
needs that module; standalone switches have no parent. Space Managers edit features in the console,
while superadmins install modules.

| Feature | Inside | Default | What it does |
|---|---|:--:|---|
| `payments.enabled` | `payments` | ● | Master switch for all online payments |
| `charges.enabled` | — | ● | Master switch for recording money owed |
| `charges.machines` | `machines` | ● | Record priced machine jobs (also needs `machine_service`) |
| `charges.bookings` | `bookings` | ● | Record priced bookings |
| `charges.events` | `events` | ● | Record paid event registrations |
| `charges.membership` | `membership` | ● | Record dues and renewal charges |
| `charges.loans` | `request_workflow` | ● | Record configured loan deposits and late fees |
| `payments.machines` | `machines` | | Online checkout for machine jobs |
| `payments.bookings` | `bookings` | | Online checkout for bookings |
| `payments.events` | `events` | | Online checkout for event registration |
| `payments.membership` | `membership` | | Online checkout for membership dues |
| `payments.loans` | `payments` | | Online collection of loan deposits and late fees |
| `mobile.push` | `mobile` | ● | Native push notifications |
| `events.offline_checkin` | `events` | | Expiring on-device roster and event-scoped PIN check-in stations |
| `machines.certifications` | `machines` | | Members need an unexpired certification per machine type to book a linked space or request work; overrides need machine-type authority and are audited |
| `notifications.delegated_recipients` | `notifications` | | Machine-scoped maintainers manage maintenance recipients for their own machines (also needs `maintenance` and `machines`) |
| `inventory.self_checkout` | — | ● | Member self-checkout and staff direct handouts |
| `presence.geofence` | — | ● | Required location check for self check-in; staff alternative |
| `inventory.kiosk` | — | | Scanner and handover Stations whose online handovers are attributed to a signed-in staff operator |

Debt recording checks **`charges.enabled` and `charges.<domain>`**, plus the domain's ordinary
pricing/rules. It needs neither gateway credentials nor the `payments` module. Tracking features
default on; a zero/free price creates no debt. Staff record offline settlement with an append-only
receipt (method, reference and received date); corrections add an amendment.

All five `payments.<domain>` switches default off outside guided setup. Online checkout needs the
opt-in `payments` module, `payments.enabled`, that domain's switch and valid Stripe/Razorpay
credentials. The core ledger remains readable and settleable when the online rail is off or removed.
`inventory.self_checkout`, `presence.geofence` and the charge-tracking master are standalone
capabilities with no parent module.

The complete feature list, including features added since this table, is in
[MODULES.md](MODULES.md#features-the-level-below-a-module).

## What you get if you choose nothing

Installing without a profile gives you **6 modules**: the six core ones. Backup and restore are
platform duties, not a module: the superadmin backs up and restores every space.
Outside guided setup, member accounts and mobile apps are opt-in; mobile pulls in `member_accounts`
when installed. Guided setup always enables per-person accounts.

The online rail is opt-in, but configured lending deposits/late fees can still create core ledger
debts through `charges.*`; missing gateway keys never suppress that record. Other domain debts need
their domain modules and pricing. Push needs FCM/APNs, chat needs its token/webhook, and sign-in
methods beyond password need their own provider configuration.

## Removing a module from the build entirely

Uninstalling is per makerspace. A deployment that will *never* use an area can drop its code surfaces
too — no routes, no admin, no OpenAPI paths — while keeping every row and migration:

```bash
docker compose run --rm --no-deps backend --role management python manage.py suggest_tombstones   # prints the line to paste
```

Add the result to `.env` as `TOMBSTONED_APPS=`. It is deliberately conservative: an app is only
suggested when **no** makerspace on the deployment uses any of its modules.
