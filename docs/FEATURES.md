# Space Works features

Everything Space Works runs today, area by area. The [README](../README.md) has the short version;
[MODULES.md](MODULES.md) explains each module key and what happens without it, and
[Choosing modules](choosing-modules.md) shows how areas, modules and features fit together.

One deployment can host **many makerspaces**. Each has its own inventory, public URL, staff,
Telegram group, QR namespace and audit scope. Queries and actions are scoped to that makerspace.

## What you can run

- **Inventory and lending.** A public catalogue by makerspace/category, reviewed borrow requests,
  staff direct handouts, and eligible authenticated QR self-checkout/return when enabled. Reviewed
  issues require a box QR scan and photo; returns require a photo and remark. Every handover is audited.
- **Machines and 3D printing.** Public print requests, machine/service queues, printers, spools,
  filament usage, slicer estimates and optional staff-private cash charges at collection; maintenance,
  certification and usage records.
- **Events.** One-off events and recurring series, approval/waitlists, ticket types, invitations,
  promo codes, account-linked speakers and claim links, collaborative hosts and participating-organization
  audiences. A simpler create form and drawer keep advanced controls under More. QR door check-in includes
  an expiring offline roster and event-scoped PIN stations. Feedback, attendance certificates,
  printable badges, owned ticket downloads and member calendar feeds complete the attendee workflow.
- **Bookings.** Bookable resources and public self-booking, recurrence, rescheduling, private
  confirmations, arrival scanning and printable passes. A requests queue, decision reasons, place-photo
  galleries and check-out remarks with issue follow-up complete the resource workflow. Public events
  show a Hosted at venue block. Both Events and Bookings support resource staff grants, draft cloning,
  answer edits, cancellation undo, curated websites, email campaigns, signed server reads and scoped
  reports through shared infrastructure.
- **People and access.** Nine fixed built-in roles per makerspace: Space Manager, Inventory Manager,
  Machine Manager, Event Manager, Booking Manager, Handover, Technician, Shop Manager and Member. Staff
  roles combine (Space Manager and Member stand alone), with per-person machine-type scope. Organizations can link spaces, publish profiles and cross-space event catalogues,
  and grant actions across the network without conferring membership identity. Superadmins use a
  separate Django control plane; see [roles and access](README-HOSTING.md#roles--access).
- **Public pages.** Makerspaces and organizations share the `/<handle>` namespace with member
  profiles. Owners save drafts and explicitly publish section layouts; events keep their existing
  website editor and gain `/e/<code>` links. Organization pages show linked public spaces and
  organized events, including a minimal past archive. See the
  [publication and portability rules](INVARIANTS.md#public-pages-shared-handles-and-owner-builders).
- **Live work and search.** Staff queues, loans and check-ins update after commit through Redis-backed
  Server-Sent Events, falling back to polling. Inventory, machine and event lists support `?q=`
  full-text search with typo tolerance. Boxes, tools and individual assets have QR/scan history.
- **Money and reports.** Track debt and offline receipts independently of optional Stripe/Razorpay
  checkout. One pricing kernel prices every charge (rate cards, item prices, member discounts, fee
  waivers); everything is free until a space sets prices. Optional GST/tax, a two-person check for
  offline income, pay links, disputes, a finance ledger with receipts, and refunds only through
  staff-approved refund cases (including offers when a price drops after people paid). Donations,
  recurring pledges, optional 80G receipts and sponsors with a public sponsor wall. Per-space Metabase
  analytics (off by default) give each space a read-only database login over curated views. Overdue tracking, CSV/XLSX exports and accessible charts with table fallbacks cover
  operations. Historical metric rollups are append-only: corrections add revisions. Every module
  has a substantive report or an explicitly gated row.
- **Notifications.** Transactional personal outboxes, verified Telegram, Slack, Mattermost, Discord
  and Twilio/Meta WhatsApp connections, Twilio SMS, per-category selection and email fallback; staff
  rooms retain their delivery matrix. Space Managers configure encrypted channel credentials. Member
  JWTs reach personal routes; browser OAuth completes through authenticated challenge verification.
  WhatsApp Twilio and Meta are registered/mounted; remaining delivery limits are recorded in the
  [delivery contract](notification-contract.md#integration-limits-in-this-tree). Sender-bound
  consent, durable STOP and per-device envelope push preserve account-only owner access independently
  of inbox installation. Sending activation and destructive retirement remain held pending
  [conversion/replay sign-off](notification-reconciliation-rollout.md). Routing to rooms and
  recipients is described in [Notification channels, rooms and recipients](notification-routing.md).
- **Accounts and profiles.** One account per person: staff roles are granted to that account, and the
  superadmin has a separate platform account. People sign in with password, Google, Apple, GitHub,
  OIDC (Keycloak, Authentik, Azure AD, Okta) or phone/SMS. Anyone with a staff role must use a second
  factor (an authenticator or a passkey), with one 3-day grace to enrol. Unusual sign-ins are checked
  and alerted ("this wasn't me" signs out everywhere), IPs can be blocked, CAPTCHA (Turnstile) and
  breached-password checks are available, and each space sets its own staff session, idle-timeout,
  passkey and staff IP rules. Member methods are switchable;
  external identity and staff-created walk-ins support spaces without the member-account ecosystem
  (see [Sign-in, identity and borrowing](sign-in-and-borrowing.md)). Opt-in maker profiles include
  projects, interests, education, optional GitHub counts and a consent-based member directory.
  Public pages at `/<handle>` add fresh publication consent, separate activity-family opt-ins,
  counts-only activity and GitHub calendars, and HOSTED/SPOKE event badges. Public reads expose
  `viewer_is_owner`; the member profile exposes this membership's `verified` flag.
- **Presence.** Time-limited member and guest check-in with project/visitor/event statuses, renewal
  prompts, a hard location check for self check-in and a staff alternative. Privacy controls govern
  the public TV display at `/m/<slug>/now`; browser GPS remains spoofable. Presence is installed on
  existing spaces by migration 0096; new spaces opt in. Defaults are 1/2/3/4 h.
- **Shop.** An optional per-space shop: consumables, kits and merch with variants, online checkout
  (Stripe/Razorpay or pay at the desk), a front-desk till with cash-ups, pickup codes and receipts. Stock
  moves only through the inventory availability module, and every sale is in the ledger.
- **ID cards.** A free-canvas card designer, digital member cards with a public validity check,
  ID programmes under membership, event badges and tickets that every event organizer can edit, wallet
  passes and door scans. Cards carry no fee.
- **Repairs and maintenance.** Members report issues on what they used; staff triage them into work
  orders, assign a Technician or an outside contact, approve quotes and track parts. Maintenance,
  To-Buy and warranty live under each area (machines, bookings, inventory). Metered machine sessions
  bill time on a machine from a QR scan, a staff start or (later) the machine itself.
- **Events depth.** Paid ticketing with orders, seats, tiers, add-ons, series passes, transfers and
  venue fees; calendar invites on confirmation emails; applications with review stages for any event;
  crew and custom check-in lists; hackathon finalists, prize payouts, entry fees and leader-pays teams.
- **Help and public stats.** An in-app help centre with role-based guides, and a public stats page per
  space (events, machines, lending, community) with a TV mode and small-number suppression.
- **Space management.** Task-grouped Space Manager navigation, a searchable settings hub and setup
  checklist; domain managers reach their own settings from their consoles. The dashboard counts
  unresolved booking issues under current booking authority and links to the issues view.
- **Modules and editions.** Install only the areas you use; uninstall hides surfaces and retains data.
  Events-only and bookings-only editions hide unused lending surfaces through `SPACEWORKS_EDITION`.
- **Operations.** `X-Request-ID` connects JSON request logs and Celery; a token-protected Prometheus
  endpoint reports queues, delivery failures and storage. Run tests locally before pushing with
  `./scripts/dev.sh test` and `./scripts/dev.sh e2e`. Actions builds/publishes backend/frontend images,
  creates the GitHub Release, promotes rolling tags and optionally deploys through a self-hosted
  runner. `security-audit.yml` runs `pip-audit` on PRs.
- **A durable handover trail.** Audit logs are append-only; attached photo metadata and scan records
  are immutable. Photo bytes can expire under a per-space retention policy with an explicit expired
  state; metadata, remarks and scans remain. A separate default-off cleanup can remove proven unused
  upload slots that never became handover evidence.

## Events programme

Hackathons, Mentor Desk, mentor rounds, volunteering and the project gallery are ordinary per-space
switches, off for a new space. See [current status](events/integration-status.md) for what has runtime
evidence. The [Events programme guide](events/README.md) links the
organizer, participant, mentor, volunteer and judge runbooks.
