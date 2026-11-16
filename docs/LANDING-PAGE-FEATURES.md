# SpaceWorks landing-page feature inventory

SpaceWorks is an open-source, self-hostable management platform for makerspaces and other shared
workshops. It brings the public catalogue and inventory loans, machine work, 3D printing, events, bookings,
membership, payments, notifications, reporting and operational records into one multi-makerspace system,
while keeping every physical handover attributable to a person and backed by evidence.

*Positioning: run the shared workshop from request to return, with proof of who handled what and when.*

## The core problem it solves

Shared tools move between shelves, boxes, members and volunteers. A spreadsheet can show a count, but it
usually cannot settle what happened when something comes back damaged, does not come back at all, or was handed out by a different volunteer.

SpaceWorks makes traceability part of the workflow rather than an optional note:

- A reviewed hardware request cannot be issued until staff scan a box QR code and attach an issue photo.
- Member self-checkout and staff direct handout require an eligible tool plus uploaded issue evidence.
- A return requires a return photo and a written remark.
- Attached issue and return photos, QR scan records and audit history are immutable or append-only; abandoned upload slots are not handover evidence.
- Lost or damaged items can close a request with an issue and connect the incident to the member's access status.
- Staff accept or reject requests in the staff console or `/control/` through the same controlled workflow; Telegram sends outbound alerts.

The result is a record of the whole handover, not just a number being decremented and incremented.

## Counted product shape

These counts were checked against the current sources rather than copied as marketing estimates:

| What was counted | Result | Source |
| --- | --- | --- |
| Module keys and customer-facing areas | **36 modules in 12 areas** | `backend/apps/makerspaces/module_registry_catalog.py`, `module_registry_definitions.py` (`GROUPS`) |
| Module modes | **6 core, 1 on by default (member accounts), 29 opt-in; 30 non-core total** | `docs/MODULES.md` |
| User-facing module entries | **36**, one per registry key | `docs/MODULES.md` |
| Seeded default roles | **10**: Space Manager, Inventory Manager, Machine Manager, Event Manager, Booking Manager, Handover, Technician, Shop Manager, Fundraising and Member | `backend/apps/makerspaces/role_catalog.py` |

The six core keys counted in the registry are Public inventory, Request workflow, Staff admin, Evidence
uploads, QR management and Scanner. The ten built-ins are fixed; eight staff roles combine, while Space Manager and Member each stand alone.

## Inventory: loans and returns

**Free / paid:** Works free. Optional rental, deposits, late, damage and lost fees use `charges.loans`; online payments are optional.

- Publish a public, makerspace-specific catalogue with categories and item detail pages.
- Let authenticated members submit borrow requests and follow their status.
- Give staff a review queue for accepting or rejecting requests, then issuing, partially returning, returning or closing them with an issue.
- Prevent staff from issuing more than the accepted quantity unless they have explicit workflow
  permission.
- Support direct counter handouts and a deliberately narrow handover console for front-desk volunteers.
- Enable self-checkout and self-return for eligible QR-tracked tools when the space chooses to offer it.
- Keep staff-issued requests, direct handouts and self-service loans in the same evidence and audit trail.
- Track what is out, who has it and what is overdue; return reminders are available from the hardware
  request system.

**Honest limits:** with member accounts enabled, submission requires a signed-in person (and current membership checks where enabled). Without member accounts, borrowers provide name, phone and a verified email code. The public
catalogue can be made effectively empty by marking every item private, but the core catalogue and loans
workflow themselves cannot be uninstalled.

## Inventory and availability

**Free / paid:** Works free. Stock, kits, transfers and stocktakes have no fee. Optional loan fees use `charges.loans`; online payments are optional.

- Manage products, categories, quantities and individually tracked asset units.
- Calculate available, reserved, issued, damaged and lost stock in one guarded availability service, with
  row-level locking and a rule that availability never goes below zero.
- Choose what the public sees for each item: an exact count, a simple Available/Limited/Unavailable label, no availability information, or no public listing at all.
- Model boxes and nested storage containers, including moves between locations.
- Import inventory from a spreadsheet with column mapping, preview and commit stages.
- Move stock within a makerspace or transfer it between makerspaces through a recorded sending and
  receiving flow.
- Run scan-first stocktakes, review variance, and commit the adjustment to the ledger.
- Maintain a procurement “to buy” list, attach receipts and move purchased items into stock.
- Generate printable QR sheets and downloadable label ZIPs in batches.

**Honest limits:** without the optional Asset units module, SpaceWorks tracks product quantities but cannot
identify which physical unit was lent. Without Stocktake, corrections are direct quantity edits rather
than a documented count session.

## QR codes and evidence

**Free / paid:** Works free. QR scans, evidence and audit history have no fee; online payments are optional.

- Generate, print, revoke and rebind namespaced QR codes for boxes, products and individual assets.
- Scan with the web camera scanner and resolve a code to its container or eligible tool.
- Preserve an immutable scan history.
- Store issue and return photos in a private S3-compatible bucket and expose them through short-lived, permission-scoped links.
- Bind presigned uploads to an allowed file type and size range.
- Upload to a staging key first, then promote evidence exactly once. The client never receives write
  access to the final evidence object, preventing replacement through a still-valid upload link.

**Honest limits:** the shipped product generates printable files but does not drive a physical label
printer directly.

## Members, identity and access

**Free / paid:** Works free. Accounts and profiles have no fee; optional membership dues, admission and guest passes use `charges.membership`. Online payments are optional.

- Give each person one account across every space; staff roles are added to that account.
- Offer username/password sign-in out of the box, with passkeys and an authenticator for two-step sign-in.
- Require two-step sign-in for anyone with a staff role, with one 3-day grace to enrol.
- Check unusual sign-ins, alert the person and offer a "this wasn't me" link that signs them out everywhere.
- Block abusive IPs, add CAPTCHA (Turnstile) and refuse breached passwords.
- Let each space set staff session length, idle timeout, passkey use and a staff IP allow-list.
- Add Google, Apple, generic OpenID Connect providers such as Keycloak, Authentik, Azure AD or Okta, and phone sign-in with SMS codes.
- Switch password, identity-provider, phone-code and self-sign-up methods independently at platform level.
- Refuse login-method changes that would leave a person with no usable credential or lock every
  superadmin out.
- Run without the built-in member-account ecosystem: staff can create named walk-in records with no
  password, while an institution can continue to use its own OpenID Connect provider.
- Handle join requests, referrals, verification, waivers, memberships and member activity.
- Offer opt-in maker profiles with projects, interests, education and, when configured, a GitHub
  contribution count.
- Publish only profiles whose owners chose to appear in the member directory.
- Record presence; self check-in needs an in-range location reading when the space sets a geofence.
- Restrict or suspend a person when accountability or access problems require it (a superadmin action).

**Honest limits:** Google, Apple, OpenID Connect and SMS sign-in need credentials from the chosen provider;
only password sign-in works without external setup. Browser location can be spoofed, so the geofence is a
deterrent, not proof. Changing a login policy does not revoke existing sessions; restriction or suspension is
the revocation path. The member sign-in screen has no "Forgot password?" link yet; the reset page is
`/reset-password`.

## Staff roles and permissions

**Free / paid:** Works free. Staff roles, scope and second factors have no paid upgrade; online payments are optional.

- Scope staff access by makerspace and by action, not by a hard-coded role name.
- Provide ten fixed built-in roles; assign combinable staff role sets within the acting manager’s action ceiling.
- Give the Technician assigned repair jobs, scheduled maintenance and machine service state, with no inventory, money or settings.
- Give the Shop Manager the shop's products, stock, prices, orders, front desk, cash-ups and shop reports, and nothing else.
- Give Inventory Managers the full hardware lifecycle without machine, staff or settings access.
- Assign Machine Managers per person by machine type; no types means no machines, and linked types include machines added later.
- Use built-in Handover for the narrow request handover, direct handout and job collection surfaces.
- Block privilege escalation: a manager cannot grant an action they do not hold, and high-risk staff and
  stock-transfer actions remain superadmin-only.
- Provide a separate superadmin control plane at `/control/`, kept off the public frontend port. The normal
  staff console remains at `/admin`.

**Honest limits:** the optional handover console and fixed built-in Handover role are separate concepts.
Handover can combine with the other four operational manager roles; its own grants remain fixed.

## Machines, jobs and maintenance

**Free / paid:** Works free. Optional jobs, materials and metered sessions use `charges.machines`; online payments are optional.

- Maintain a machine registry with operators, images, documents, usage, warranty records and consumable pools.
- Accept machine service requests, collect uploaded job files and manage a staff work queue.
- Record which machine ran a job, who operated it, material consumption and the resulting usage entry.
- Narrow machine access per staff role rather than exposing every machine to every maintainer.
- Schedule preventive maintenance and record completed repairs in maintenance logs with supporting documents.
- Hand completed machine jobs back to their owners through the scoped handover workflow.
- Run one job flow for every machine type, with quotes, a "needs a booking" rule, lockout, downtime and work orders.
- Let members report issues on what they used; triage them into work orders for a Technician or an outside contact.
- Meter machine time in sessions started by a QR scan or by staff, with auto-stop and staff-confirmed charges.

**Honest limits:** without the Machine service module, machines are records rather than a job queue. The
system records machine work but does not read live state from printers, CNC controllers or other hardware:
only the server side of a device protocol ships (see `docs/machine-integrations/INTEGRATION.md`).

## 3D printing and filament

**Free / paid:** Works free. Optional print/material charges use `charges.machines`; online payments are optional.

- Accept public print requests and files.
- Manage printers and spools, track filament use and store slicer estimates.
- Present print-specific intake and queue views on top of the general machine service workflow.
- Support an optional staff-private cash charge at collection.
- Use the broader Payments module when online checkout, receipts and reconciliation are required.

**Honest limits:** 3D printing is part of Machine service, which handles every machine type; there is no
separate Printing module (retired in 0.12.0). Without Machine service a 3D printer can still be registered as
a machine, but no job queue, print form or print tracker is offered.

## Events and bookings

**Free / paid:** Works free. Optional tickets, teams, entry fees, deposits and venue fees use `charges.events`; resource/time fees use `charges.bookings`. Online payments are optional.

- Publish events, accept member registrations and let staff register a person from the console.
- Check attendees in by QR code and retain attended-event history on opted-in maker profiles.
- Run collaborative events across makerspaces with collaborator records and host-waiver acceptance.
- Define bookable resources and rules, manage reservations, and offer public self-booking.
- Include bookings in member activity history.
- Optionally charge for event registrations and bookings through the same payment system used by other parts of the platform.
- Sell tickets with orders, seats, tiers, add-ons, series passes and transfers; charge venue fees for hosting.
- Take applications for any event through review stages; manage crew and custom check-in lists.
- Run hackathon finalists, prize payouts, entry fees and leader-pays teams.
- Attach a calendar invite to registration and booking confirmation emails.

**Honest limits:** Events and Bookings are separate optional modules. Removing either removes its public
listing and staff workflow, and makes its matching payment switch inert.

## Payments

**Free / paid:** Works free. A fully free space turns `charges.enabled` off. Otherwise each `charges.<domain>` switch controls recording debt; `payments` adds only the optional Stripe/Razorpay rail. Offline settlement always records a receipt.

- Take online payments through Stripe or Razorpay behind a common payment workflow.
- Create charges and receipts for machine jobs, bookings, events and membership dues.
- Settle checkout and webhook updates, reconcile payments, and keep payment records attached to a stable
  description even if the originating optional module is later removed.
- Support managed Stripe Connect resolution and an in-app PaymentSheet when the mobile substrate is also
  enabled.
- Enable payments globally and then independently for machines, bookings, events and membership.
- Price every charge through one pricing kernel: rate cards, item prices, member discounts and fee waivers.
- Record tax (GST), offline income with an optional two-person check, pay links, disputes and a finance ledger.
- Refund only through staff-approved refund cases, including offers when a price drops after people paid.
- Take donations and recurring pledges, issue optional 80G receipts and show sponsors on a sponsor wall.
- Run an optional per-space shop with online checkout, a front-desk till and cash-ups.

**Honest limits:** installing Payments does not begin charging. The master switch, the relevant area switch
and valid provider credentials must all be present. Payment records are deliberately not erased by a
module-data purge because they record real money movements.

## Notifications and integrations

**Free / paid:** Works free. No member fee; external delivery providers can charge the operator. Online payments are optional.

- Provide an in-app inbox with read/unread state.
- Send makerspace mail through that space's SMTP configuration; account recovery and verification use platform mail so disabling tenant email cannot lock users out.
- Send alerts to Telegram, Slack, Mattermost and Discord. Each outbound channel is an independent module.
- Review hardware requests in the staff console or `/control/`; Telegram alerts carry no decision buttons.
- Create multiple chat rooms and narrow each one by machine, machine type or inventory category.
- Choose notification recipients by role, named member, all members or the person the event concerns,
  while still respecting that person's permissions and notification preferences.
- Edit email templates for hardware, printing, events, bookings, maintenance and membership; edit one chat
  message body shared across all four chat channels.
- Register and revoke attested device sessions and send native push when a compatible app is connected.
- Encrypt per-makerspace Telegram and SMTP secrets at rest, expose them as write-only settings, and keep
  one makerspace's integrations isolated from another's.

**Honest limits:** enabling a channel does not configure it. Email needs SMTP credentials; Telegram needs a
bot and chat; Slack, Mattermost and Discord need webhooks; push needs FCM or APNs. Native push and device-session
support ship on the server; Android and iOS clients are linked from the hub.

## Reporting and analytics

**Free / paid:** Works free. Reports, charts, stats and exports have no member fee; online payments are optional.

- Show operational dashboards and an inventory ledger.
- Report what is issued, who holds it, overdue items and problem records.
- Use a central report registry so inventory, machine and event reporting can share one export surface.
- Export registered reports as CSV or XLSX.
- Give each space an optional read-only Metabase login over curated views, embedded in the console.
- Publish a public stats page per space with a TV mode and small-number suppression.
- Keep Reports independent from Inventory so machine and event reports do not vanish because an inventory
  option changed.

**Honest limits:** without the Reports module, the console has no analytics screens or report exports; the
underlying operational records remain owned by their original modules.

## Multiple makerspaces and organization accounts

**Free / paid:** Works free. Organization links, permissions and public profiles have no member fee; online payments are optional.

- Host many makerspaces on one deployment. Each tenant owns its inventory, public URL, staff memberships, ten built-in role instances, integrations, QR namespace and audit scope.
- Keep public and staff queries scoped to the selected makerspace.
- Move stock through an explicit cross-makerspace transfer rather than silently changing another tenant's
  count.
- Represent a network, university or chain as an organization linked to several makerspaces as owner,
  manager or affiliate.
- Give organization staff selected actions across linked spaces without creating a separate login and
  duplicate membership in every space.
- Keep organization authority separate from identity and expose cross-organization reach in a dedicated,
  read-only view rather than mixing it into the local staff roster.

**Honest limits:** integrations are stored per makerspace; there is no shared SMTP or Telegram credential
object for an organization. Spaces that share a service enter the same credential independently.

## API access for integrators

**Free / paid:** Works free. Scoped API access has no member fee; online payments are optional.

- Expose documented REST APIs with OpenAPI schema, Swagger UI and ReDoc.
- Issue API clients with encrypted HMAC secrets and versioned scopes.
- Maintain a registry mapping each scope to the protected routes it may call, with deployment checks that reject newly protected routes that were not classified.
- Support API-key access requests and staff-controlled client issuance.
- Keep browser and API access tenant-scoped rather than trusting a client-supplied makerspace alone.

**Honest limits:** API access is not a universal master key. Clients must sign requests and hold a scope
registered for the exact protected route.

## Backup, export and data ownership

**Free / paid:** Works free. No member fee for backup, export or portability; online payments are optional.

- Back up and restore a whole deployment, including recovery controls that quarantine normal application
  traffic while restoration is in progress.
- Let a Space Manager export tenant data in redacted or portable forms.
- Move one makerspace from a hosted deployment to its own server as an `age`-encrypted archive containing its rows, approved personal data and uploaded files.
- Require explicit approval of the people whose contact details will travel in a tenant migration; carry
  unapproved people as opaque references.
- Freeze source writes for the final snapshot and keep the destination closed until rows and files verify,
  so both deployments are not writable during cutover.
- Archive the source tenant after migration rather than silently deleting the accountability record.
- Keep module uninstall reversible by retaining its rows; make destructive module-data purge a separate,
  confirmed, superadmin-only operation.

**Honest limits:** an archived source tenant is outside the normal purge guarantee. A failed object deletion
does not release its storage quota, and financial records survive module purges. Those choices favour an
accurate record over a cosmetically empty database.

## Security and privacy

**Free / paid:** Works free. No security upgrade is paid; online payments are optional.

- Isolate each makerspace's records and scope staff permissions to both tenant and action.
- Keep evidence in private object storage and serve it only through short-lived signed URLs to active,
  authorized staff.
- Keep integration secrets encrypted at rest and write-only in staff-facing APIs.
- Make attached evidence and QR scan records immutable and the audit log append-only, including database-level
  protection for audit rows.
- Rate-limit login and public request submission, lock out repeated admin-login failures, and use a hidden honeypot field against automated public submissions.
- Apply production security headers and an always-on Content Security Policy; run dependency auditing in
  continuous integration.
- Restrict the superadmin control plane to superadmins and keep it off the public frontend port.
- Allowlist public inventory fields so storage locations, box IDs, QR data, scan history, evidence,
  requester history and hidden counts never appear in public responses.
- Force the generated first administrator to change the setup password on first login.

**Honest limits:** TLS is supported but disabled by default in the installer and must be enabled for a
production deployment. Self-hosters remain responsible for host security, backups, provider credentials
and operational monitoring.

## Shop

Products, variants, stock holds, kits, pickup, front-desk sales, receipts, returns and cash-ups use the
same inventory and ledger services as other areas. Turning charges off refuses new sales
without removing the stock, access or audit rules.

**Free / paid:** Catalogue, stock, consumables and staff management work free. Selling requires
`charges.enabled` plus `charges.shop`. Offline cash with a receipt works when they are on; online
payments are optional. Charges off retains saved prices, existing debts and catalogue data.

## Donations and sponsors

Campaigns, sponsor tiers, recognition and a public sponsor wall work without collecting money. Gifts,
pledges and sponsor charges are recorded once in the donations ledger, with optional tax-exempt receipts.

**Free / paid:** Works free for campaigns and recognition. Accepting real money requires
`charges.donations` and the master switch; online payments are optional and offline gifts get a receipt.

## Presence and public TV

Time-limited member/guest check-in, a location check for self check-in, a staff alternative and privacy
controls feed paired workshop screens. Screens show only public data from the areas that are enabled.

**Free / paid:** Works free. No presence or display fee; online payments are optional.

## Mobile apps and connected devices

Android and iOS sessions, per-device notifications and the optional payment sheet share the server's
limits and charge decisions. Signed printer/label devices, adapters, telemetry and camera records use
scoped device credentials, not staff accounts.

**Free / paid:** Works free. Devices have no separate fee. Priced machine work uses `charges.machines`;
the optional native payment rail uses the same area switches as the web.

## Public pages, repairs and help

Space, organization, event and booking website builders publish explicit drafts. Repair issue reports,
work orders, technicians, preventive maintenance and To-Buy lists stay within their owning area. The help
centre, public stats, schedule and Space Manager setup tools are also available without charging members.

**Free / paid:** Works free. Publishing, repairs management and help have no fee. Borrower damage fees
use `charges.loans` and priced machine jobs use `charges.machines`; online payments are optional.

## Landing section coverage and limits

The hub's existing six interactive area tabs are followed by **Every area can run free**. Its 19 entries
cover the 12 registry groups plus shared product areas, each with a free/paid note. The list is in
`frontend/src/features/hub/landing/FeatureCoverage.tsx`; the component is rendered by `AreasSection.tsx`.
It inherits the landing typography and semantic ink/muted tokens, with no section border or background
band, and has light/dark content regression tests in `FeatureCoverage.test.tsx`.

[Limits](LIMITS.md) lists all registered quotas and the discovered input/upload bounds. [Features](FEATURES.md)
and [Free and paid](../README.md#free-and-paid) carry the same seven charge switches. Source inventory
is not a claim that every surface or condition has passed execution; test execution belongs to the
orchestrator for this run.

## Modules and positioning

The [landing-page modules and positioning](LANDING-PAGE-POSITIONING.md) companion contains
the optional-module comparison, feature switches, audiences, deployment options, differentiators
and features that have not shipped.
