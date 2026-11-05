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
- **People and access.** Seven fixed built-in roles, combinable staff assignments and per-person
  machine-type scope. Organizations can link spaces, publish profiles and cross-space event catalogues,
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
  checkout. Overdue tracking, CSV/XLSX exports and accessible charts with table fallbacks cover
  operations. Historical metric rollups are append-only: corrections add revisions. Every module
  has a substantive report or an explicitly gated row.
- **Platform overview (superadmin).** One page in the web superadmin console totals every live
  space: people, lending, machines, events, bookings, membership, money and operations, each total
  beside its per-space table, with this month / this year / all time / custom periods, a toggle for
  archived and not-serving spaces, drill-down into each space and an audited CSV. Money stays per
  currency, a block hides where its module is off everywhere, and no member name is shown. See
  [MODULES.md](MODULES.md#the-platform-overview-superadmin-not-a-module).
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
- **Accounts and profiles.** Separate member, tenant staff and platform accounts. Members use
  password, Google, Apple, GitHub, OIDC (Keycloak, Authentik, Azure AD, Okta) or phone/SMS;
  staff/platform use password plus authenticator MFA where required. Member methods are switchable;
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

## Events programme (pre-release)

The expanded Events programme is at an **integration checkpoint**, with its new features
off by default. See [current status and remaining work](events/integration-status.md)
before enabling hackathons, Mentor Desk, volunteering or project gallery. Schema/routes
alone do not establish release acceptance. The [Events programme guide](events/README.md) links the
organizer, participant, mentor, volunteer and judge runbooks.
