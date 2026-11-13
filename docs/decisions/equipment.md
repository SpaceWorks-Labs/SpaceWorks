# Decisions: Equipment and machines

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-343 — Generic "Add a machine type" setup
- **Area:** equipment
- **Date:** 12 November
- **Decision:** One step-by-step wizard works for any machine type, optionally prefilled from a seeded, editable template catalogue (data, not code), covering basics, consumables, intake fields, pricing, access, bookings, safety and adapter profile, maintenance schedule, event purpose, notifications and notes. Every step stays editable from the type page.
- **Why:** No hard-coded printer, laser or mill screens.
- **Status:** current
- **Implemented in:** `backend/apps/machines/`

### D-341 — Per-machine-type consumable profiles
- **Area:** equipment
- **Date:** 12 November
- **Decision:** When creating or editing a machine type, staff choose its consumables from templates or add their own, each with unit and measurement, required-on-job flag, estimation and recording rules, pricing, stock link to inventory pools and low-stock alerts. Existing data migrates without loss, and intake, quotes, adapter reports and reports follow the type's profile.
- **Why:** A 3D printer, laser cutter and PCB mill do not consume the same things or quantities.
- **Status:** current
- **Implemented in:** `backend/apps/machines/`

### D-331 — Shelf pointer: API only, no hardware in repo
- **Area:** equipment
- **Date:** 11 November
- **Decision:** Staff get "Show on shelf" on item, box, location and handout screens, a pointer-guided stocktake and a "Check shelves" shift saved as an audited shelf-check record, all staff-only. No hardware adapter lives in this repo; the API publishes `pan_tilt` and `led_segment` pose schemas, embedded-friendly responses (Ed25519 and SHA-256 only, a time endpoint) and server-enforced laser caps (`laser_max_power_pct`, `max_on_seconds`; clear is always allowed). The simulator is a test helper in the conformance kit.
- **Why:** Both a Raspberry Pi and an ESP32 pointer must be servable by the same API; locations never leave the server except as the pose to the owning adapter.
- **Status:** current
- **Implemented in:** `backend/apps/devices/models_shelf_check.py`, `docs/device-adapters/`

### D-321 — Media and data capabilities of the adapter API
- **Area:** equipment
- **Date:** 11 November
- **Decision:** The adapter API adds audio (receive-only by default, two-way talk staff-only and audited, audio recording off and separately consented), adapter-uploaded artifacts with retention and quotas, detection events that only notify, telemetry history with downsampling, diagnostics, a signed offline access cache per binding, and remote config push with time sync. Switches default off and limits default to none.
- **Why:** Researched against common printer, camera and door-control platforms so adapters have what they need.
- **Status:** current
- **Implemented in:** `backend/apps/devices/`, `docs/device-adapters/`

### D-320 — No automation engine in core
- **Area:** equipment
- **Date:** 11 November
- **Decision:** Core provides the Device Adapter API only (data sync, job dispatch, control, labels, locate, kiosk, media) plus the server-side safety settings (idle auto-off, area clear, max session, filter interlock). Rules and automation logic live in adapters in separate repositories.
- **Why:** The maintainer judged an in-core rules engine unnecessary.
- **Status:** current

### D-319 — Machine access grants replace certification gating
- **Area:** equipment
- **Date:** 11 November
- **Decision:** Machine use is gated by an explicit access grant that a Space Manager (or a Machine Manager in scope) gives a member per machine and/or machine type, with optional expiry and note, revocable and audited. A machine can instead be open to all members. Certifications, trainings and inductions no longer gate machine use anywhere and are retired as a feature: existing records stay as read-only history and are converted to grants by a migration so nobody loses access. Access reason codes are `no_machine_access` and `machine_access_expired`. A machine-level supervision rule stays separate.
- **Why:** Space managers want to decide who may use each machine without a certification workflow.
- **Status:** current
- **Implemented in:** `backend/apps/machines/`

### D-312 — Device Adapter API v1 with every capability at API level
- **Area:** equipment
- **Date:** 11 November
- **Decision:** One uniform Device Adapter API serves machines, inventory devices (shelf pointer, label printers, scanners), doors and sensors. An adapter binds to any target and declares capabilities, each with a versioned JSON Schema vocabulary: status, telemetry, events, job dispatch, file fetch, control, access authorize, sessions and usage log, consumables, server-enforced safety, maintenance report, locate indicate and calibrate, label print, scan report, sensor report, door access, snapshot and stream, and a public-checkout kiosk capability. Every effect still goes through the owning workflow (machine service, inventory, QR/box, evidence); the kiosk can never bypass evidence, eligibility or audit. The console stays small (enroll, bind, status, revoke, basic watch and logs).
- **Why:** The maintainer wanted one uniform API so adapters can be built later in other repositories.
- **Status:** current
- **Implemented in:** `backend/apps/devices/`, `docs/device-adapters/`

### D-311 — Machine connectivity area (video, logging, notifications)
- **Area:** equipment
- **Date:** 11 November
- **Decision:** Extends the adapter work with usage logging per session/job feeding reports and the charge-tracking ledger, notifications through the catalogue (job finished, failed, offline, maintenance due and similar), and camera-while-watched video (staff, and the job owner for their own job, only; no recording by default). Per-machine-type adapter profiles and rich video UI were deferred by D-312(d); the automation parts were dropped by D-320.
- **Why:** Informed by behaviour of existing makerspace tooling (research only, nothing copied).
- **Status:** partly superseded by D-312 and D-320

### D-310 — Uniform, vendor-neutral adapter API in core
- **Area:** equipment
- **Date:** 11 November
- **Decision:** Core ships one stable, vendor-neutral adapter API built on the `devices` app; an adapter authenticates as an enrolled device (Ed25519 signed requests, rotation, revocation) and may manage many machines through explicit bindings. Vendor adapters (Bambu, Prusa, OctoPrint/Klipper, laser/CNC controllers) live in separate repositories. The API covers job leasing with idempotent reports, status, commands, events and access control. Every state change still goes through the machine-service workflow and the adapter is never an audit actor. The whole thing is gated by `machines.integrations`, default off.
- **Why:** The maintainer wanted third parties to build adapters without a second bearer-token API.
- **Status:** partly superseded by D-312
- **Implemented in:** `backend/apps/devices/`, `docs/device-adapters/`

### D-309 — Machine printing automation scope for 0.12.0
- **Area:** equipment
- **Date:** 11 November
- **Decision:** 0.12.0 ships the existing printing foundation (signed printer enrollment, printer bindings, job queue pull, start/finish/fail reports through the machine-service workflow, heartbeat snapshot, label printers, member print requests) with `machines.integrations` hidden and off. Vendor-specific printer agents and fleet scheduling are left to later work.
- **Why:** Keep the release to the already-built foundation.
- **Status:** partly superseded by D-310
- **Implemented in:** `backend/apps/devices/`

### D-230 — Machines audit follow-ups
- **Area:** equipment
- **Date:** 10 Nov 2026
- **Decision:** Per-type job/session settings reads need the same type authority as writes (404 otherwise). Only retired machines refuse bookings (offline machines stay bookable, lockout and repair rules still apply) and device sessions never block a job start. A guest's machine-time booking counts as job use, a minor can never be a supervised-session instructor, resubmitting a job re-runs intake gates, and machine-linked bookable resources take no bookings with `machines.time_booking` off.
- **Why:** MACHINES-AUDIT-0.12.0.
- **Status:** current

### D-221 — Lending, events, repairs, notifications and feeds
- **Area:** equipment
- **Date:** 9 Nov 2026
- **Decision:** Self-renewal for account-only borrowers is a Space Manager setting (default off). Event equipment gets time-window availability, bulk and shared planning that keeps per-person accountability, a per-event return window, an organizer certification check and event-only lending. A damaged return hands off to repairs with the same notices as a reported issue and the borrower is told when the repair closes. Membership plans gain included booking/machine hours consumed before pricing. Print and per-machine intake require `machines.job_requests` on the server. Notifications for lending, events, bookings, membership and shop pickup go through the notification module with preferences; `maintenance.calendar_feed` also gates maintenance in the combined feed. Shop staff cannot hand over an order with an interrupted event pickup until it is moved, and shop order fulfilment webhooks are added. Co-organizers limited to a track or window may invite helpers limited the same way.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** docs/loan-policy.md, docs/member-account-renewals.md, docs/notification-contract.md

### D-214 — Contextual inventory lending
- **Area:** equipment
- **Date:** 8 Nov 2026
- **Decision:** Inventory can be lent for an event, a specific booking, both, or neither (ordinary loan). The actual recipient stays individually accountable even under an organizer's bulk allocation; event/booking is context, never a second stock deduction or loan state machine. It reuses the request workflow, availability owner, QR/evidence/audit and core charge ledger; Event or Booking Manager authority does not grant inventory actions. Ending an event or booking never silently returns items, erases evidence or cancels debt, and the optional associations live in removable adapters so core lending gains no dependency on optional apps. Event-wise and booking-wise reporting deduplicates a loan with both contexts.
- **Why:** Reason not recorded
- **Status:** partly superseded by D-216
- **Implemented in:** docs/equipment-contexts.md, docs/equipment-reports.md

### D-197f — Misc parity fixes: maintenance refusal, ESLint, trust, rename
- **Area:** equipment
- **Date:** 5 Nov 2026
- **Decision:** Only machine status `maintenance` refuses machine bookings (not `offline`); the repair window runs from downtime start to `expected_back_at` (no end means every later booking) and bookers are emailed once on entering repair. Gallery filters travel as a `filters` key beside the gallery page. Operator trust of a space comes from the writer (superadmin) with the save-time auto-trust hook removed, and the hide switch goes through the settings authority. The frontend gets an `eslint.config.js` (recommended plus typescript-eslint plus classic hook rules, exhaustive-deps as a warning).
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** frontend/eslint.config.js, backend/apps/makerspaces/capability_definitions_parity.py

### D-174 — Walk-in sessions cannot submit machine jobs
- **Area:** equipment
- **Date:** 3 November
- **Decision:** Walk-in claim sessions are refused on the machine-job upload and submit routes (the old printer route allowed them). Walk-ins get machine work through a staff-created request.
- **Why:** Job requests come from checked-in members (D-140, D-142), and a walk-in claim session is not a member.
- **Status:** current

### D-158 — Metered machine sessions
- **Area:** equipment
- **Date:** 1 November
- **Decision:** An optional per-space `machines.sessions` switch (off by default) records machine usage sessions started by a member scanning the machine QR, by staff, or automatically from an integrated device. Starting requires a valid certification when the type needs one, an open check-in, and no conflicting booking. Billing uses an hourly rate per machine type rounded per minute with an optional minimum; the charge is created pending and staff confirm it. Sessions auto-stop at a maximum length (default 4 h), at check-out and at closing time, flagged for staff correction. History is append-only with audited amendments. Prepaid credits, plan-based access windows, training courses, document attachments and a device access API were declined for this release.
- **Why:** Money must never move without staff approval.
- **Status:** current
- **Implemented in:** `backend/apps/machines/models_sessions.py`, `backend/apps/machines/notifications_sessions.py`

### D-142 — Machine job policy answers
- **Area:** equipment
- **Date:** 29 October
- **Decision:** Submitters must be members of that makerspace and checked in (with a signed waiver if waivers are on). Quotes are set per machine type (valid 7 days, reminder day 5, auto-cancel). Payment is per type: approve now and pay at completion by default, with a per-space "pay before pickup" switch or prepay per type. Actual usage is charged, capped at the quote. Failure charging is configurable per space and machine type (no charge by default, material only, or full), with space/machine faults re-queued free at the front (max two automatic attempts). Staff can reorder, pin urgent jobs and start several jobs together as a batch run. Uncollected jobs get reminders on days 3 and 10 and staff can mark NOT COLLECTED from day 14 (the charge stays owed; three no-shows in six months flags the member, with no automatic ban). Pickup is by the member or anyone with the job's pickup code. Per-type limits (open jobs, job length) are off by default; a "runs unattended" flag decides whether ETAs count opening hours only. Members cancel only before In progress.
- **Why:** Reason not recorded
- **Status:** partly superseded by D-174
- **Implemented in:** `backend/apps/machines/job_policy.py`, `backend/apps/machines/job_charges.py`, `backend/apps/machines/job_pickup.py`, `backend/apps/machines/models_job_batch.py`

### D-141 — Machine job lifecycle and visibility
- **Area:** equipment
- **Date:** 29 October
- **Decision:** Every job moves through Submitted, optionally Quote sent and Awaiting approval or payment, In queue (live position, "You're next", ETA), In progress (on a named machine), Done or Ready to collect, and Collected. Needs changes, Rejected, Failed and Cancelled are the side states. Members see a timestamped timeline, position and ETA; staff get a per-machine queue board (reorder, assign, start, finish). Every transition is audited, notified, and money goes through the ledger.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/machines/service_queue_eta.py`, `backend/apps/machines/job_order.py`

### D-140 — One uniform "Request a job" flow for every machine type
- **Area:** equipment
- **Date:** 29 October
- **Decision:** Every machine type with service turned on (printer, laser, CNC, vinyl, PCB mill and so on) uses one member-only job request flow: pick machine or type, upload files in the formats accepted for that type, add material and notes, then share the same queue, status page, quote-and-approve, ETA, payment, ledger and notifications. The old 3D-printer routes stay as aliases. Each machine type can be switched on or off per space.
- **Why:** Only the 3D printer had a public submission route although the underlying model, queue and status page were already shared.
- **Status:** current
- **Implemented in:** `backend/apps/machines/models_service_requests.py`, `backend/apps/machines/job_intake.py`

### D-103 — Issue reporting by users
- **Area:** equipment
- **Date:** 24 October
- **Decision:** The borrower of an item, the person who booked a room and the owner of a machine job can report an issue (account-less borrowers through their verified email). A report notifies the area manager and the Space Manager, the manager fixes it or sends it to technicians, and the reporter is told when it is fixed. Every step is audited.
- **Why:** Reason not recorded.
- **Status:** current

### D-98 — Technician contacts and request sends
- **Area:** equipment
- **Date:** 24 October
- **Decision:** A space saves many technician contacts with phone, email, chat handles, covered areas and notes. When an issue is reported staff select which technicians to notify, it goes out by each one's chosen channels, and each send (recipient, time, channel, delivered or failed) is recorded on the issue history. Defaults can be preselected per area or machine type.
- **Why:** Reason not recorded.
- **Status:** current

### D-93 — Technicians and repairs
- **Area:** equipment
- **Date:** 24 October
- **Decision:** Each space keeps technician contacts, either staff with a Technician role or outside contractors with no account. Coverage is a per-space switch per kind (machines, inventory items, rooms, where a room out of service blocks or warns on bookings). Reporting a fault only notifies; staff record the visit, remarks, photos, parts (which go to To-Buy), quote, approval and payout, and money is never sent automatically.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/maintenance`

### D-76 — Machine integrations limited to a device API
- **Area:** equipment
- **Date:** 22 October
- **Decision:** No vendor integrations or fleet sync are built. Only the server side is provided for a future device agent: registration and token, status and job report endpoints, documented in OpenAPI, off by default. Restore drills use a throwaway server identity and isolated database and never touch live data or keys.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/devices`, `docs/device-protocol.md`

### D-58 — Cancelling a running machine job
- **Area:** equipment
- **Date:** 20 October
- **Decision:** Cancelling a running machine job records the material used so far as a space cost with no charge to the member. The cancel form has an optional "material used so far" field prefilled from elapsed time over estimated duration, and the confirmed amount is consumed from stock.
- **Why:** The space bears the cost of a job it cancels, not the member.
- **Status:** current
- **Implemented in:** `backend/apps/machines`

### D-44 — Machine job queue ETA
- **Area:** equipment
- **Date:** 18 October
- **Decision:** Every machine type with a service queue shows an estimated start and finish time, computed by simulating the queue across compatible machines in parallel rather than summing durations. It is labelled an estimate, degrades honestly when estimates are missing, and sends notices when you are next, when the job starts and when it finishes. Cancellation recomputes the queue immediately and releases held consumables with no charge to the requester.
- **Why:** A plain sum of print times would mislead requesters.
- **Status:** current
- **Implemented in:** `backend/apps/machines/service_queue_eta.py`, `backend/apps/machines/service_queue_notices.py`
