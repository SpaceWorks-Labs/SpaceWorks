# Decisions: Modules and areas

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-340 — Printing folded into Machine service; Spaces link
- **Area:** modules
- **Date:** 12 November
- **Decision:** The `printing` module is retired and folded into `machine_service`, which covers service requests for every machine type; `printing` remains a readable retired alias so stored switches, backups and API clients keep working. The landing "Find a space near you" section is removed while the header Spaces link and `/spaces` stay.
- **Why:** One module should cover service requests for all machine types.
- **Status:** current

### D-329 — Module-audit follow-ups
- **Area:** modules
- **Date:** 11 November
- **Decision:** After a wallet-pass feature is switched off, wallet updates still flow but only to void or expire existing passes. The two certification reports become read-only retired history, the module screen shows a `not_shipped` lock reason, and Anthias routes return the typed `feature_disabled` 404.
- **Why:** A revoked pass must never look valid, and gated routes must answer uniformly.
- **Status:** current

### D-328 — Per-module limits and the /features pages
- **Area:** modules
- **Date:** 11 November
- **Decision:** Every module gets limits in the limit registry, all off (unlimited) by default. The superadmin sets a platform default and per-space overrides, Space Managers see usage read-only, a warning appears at 80% and new items are blocked at 100% while existing data is untouched. The landing `/features` page has a grid with a `/features/<module>` page per module.
- **Why:** Operators need to cap usage without it being on by default.
- **Status:** current

### D-324 — Module audit, module screens and colour settings
- **Area:** modules
- **Date:** 11 November
- **Decision:** All module and feature keys were audited at platform and per-space level (routes refuse, navigation hides, tasks skip, parent/child rules) with parametrised gating tests. The module switch screens are grouped by area and role with clear states and reasons, and per-space colour settings get live previews, contrast checks and presets for light and solid-black dark.
- **Why:** Switches must behave identically everywhere, and managers need to understand what each one does.
- **Status:** current

### D-293 — Derived organization membership and one member card
- **Area:** modules
- **Date:** 11 November
- **Decision:** A person with an active community membership in a space an organization owns (owner link only) counts as a member of that organization, computed live from the space membership with no copied rows. It counts for audiences, member roll-up (counts only, never names) and cross-space eligibility, but never grants governor seats or authority and never exposes personal data across spaces. A member gets one member ID card (one number, QR and verify page) that serves as both space and organization card; event badges and staff ID cards remain separate card types.
- **Why:** Live derivation cannot drift; one card avoids duplicate credentials.
- **Status:** current
- **Implemented in:** `backend/apps/organizations/derived_membership.py`, `backend/apps/organizations/org_member_rollup.py`

### D-292 — Organizations: home space, units and member cards
- **Area:** modules
- **Date:** 11 November
- **Decision:** An organization's members, plans and cards live in its home space; districts, chapters and branches are units inside that space (tree up to four levels, unit-scoped local staff, while organization-derived and superadmin authority are never unit-scoped). There is no separate organization-level membership model, because organizations must not hold money or personal-data keys. The public verify page shows the holder's name by default for new spaces (holders can hide it) and never the card image. Organization ownership transfer is not added.
- **Why:** Invariants forbid organizations holding money or personal data; units give hierarchy without a second membership model.
- **Status:** current
- **Implemented in:** `backend/apps/organizations`

### D-270 — Organization hours bank
- **Area:** modules
- **Date:** 11 November
- **Decision:** Each organization has a per-space hours allowance plus an append-only signed-minute ledger (grant, adjust, consume, release); the balance is derived per UTC period key, never stored. Organization bookings draw from the bank before any charge, cancellation releases once, and time edits needing a different period or more hours need a price confirmation. Manual adjustments need a reason and cannot go below zero. It works only with bookings and `bookings.organization_bookings` on. Bank rows are omitted from tenant exports and purged with the bookings module.
- **Why:** Organizations need prepaid booking hours; the organization is deployment-global, so rows are not exported per space.
- **Status:** current
- **Implemented in:** `backend/apps/organizations`, `backend/apps/bookings`

### D-266 — Notification and role-scoping outcomes from open-items batch 1
- **Area:** modules
- **Date:** 11 November
- **Decision:** Shop and Safety stay display-only notification families (shop notices remain in the `payments` family); the default loan reminder stays at 24 hours; event-loan notices are a context kind linking to the event; the waiver gate without passes is a guest-pass policy flag, default off; `ReportDefinition.required_action` defaults to MANAGE_MAKERSPACE; incident alerts reach area managers through `fanout(staff_extra_ids=...)`; facts outside the actor's scope answer 404.
- **Why:** Reason not recorded
- **Status:** current

### D-254 — Every area, including Inventory, is switchable per space
- **Area:** modules
- **Date:** 10 November
- **Decision:** A space-level Inventory area switch hides every inventory surface when off (staff tabs, public catalogue, member borrowing, self-checkout, kiosk, reports, dashboard tiles, related notifications) while the core safety models (requests, handovers, evidence, QR, accountability) stay installed and data is kept. It defaults on for existing spaces and new installs; the installer's setup-areas question and the first-run wizard can switch it off. Every area combination must yield a sensible home, nav, public site and dashboard with no empty pages, and tests pin each combination.
- **Why:** Some makerspaces do not need inventory, shop, events or booking.
- **Status:** current
- **Implemented in:** `backend/apps/makerspaces`, `docs/MODULES.md`

### D-228 — Module on/off follow-ups
- **Area:** modules
- **Date:** 10 Nov 2026
- **Decision:** Event-only items stay unlendable while Events is off, and the public item page shows a neutral "Not available to borrow right now". Per-space Metabase analytics views return no rows for an area whose module is off; data is retained and reappears when switched back on.
- **Why:** Consistency with D-218.
- **Status:** current

### D-218 — Switching a layer off removes it everywhere
- **Area:** modules
- **Date:** 9 Nov 2026
- **Decision:** A retained room outage refuses, warns and shows only while `bookings.room_maintenance` is on and the maintenance app ships; a bookable machine's repair window applies only while the `machines` module runs. One predicate each (`room_outages_apply`, `machine_repairs_apply`) is used by admission, readiness and the busy overlay so they never disagree. Records are retained when switched off.
- **Why:** R1/R2 findings of the module on/off audit.
- **Status:** current
- **Implemented in:** backend/apps/bookings/admission.py, backend/tests/bookings/test_switch_off_layers_r1r2.py

### D-200c — Module and money audit outcomes
- **Area:** modules
- **Date:** 6 Nov 2026
- **Decision:** Membership capability gates raise a typed SurfaceOff. Payment rail fields answer 404 with `payments` off, while loan rules and currency on the same row stay writable. Free series passes read "Free" and buying stays possible (the server decides the money). `/control/` audit rows carry field names only, and wrapper action labels are derived from the action key. Channel setup hides channels whose module is off.
- **Why:** Reason not recorded
- **Status:** current

### D-197c — Module separation: field-level refusals stay 400, module-off routes answer 404
- **Area:** modules
- **Date:** 5 Nov 2026
- **Decision:** Field-level "feature off" refusals inside otherwise live routes stay 400, and settings-write 403 `feature_disabled` is unchanged. Kiosk replay and capabilities enforced in a serializer answer 404, with the 404 body carrying the switch key. Notification event overrides can only narrow, never widen. Scheduled tasks are gated by module (waitlist lapses on `loans.waitlist`, report rollups on `reports`, both catching up on re-enable) except the core loan spine, payment ledger, money in flight, delivery infrastructure and retention. The task-to-module map lives in `operations/cloud_jobs/task_sources.py` with a guard that fails on an unmapped task; a bulk import with its module off fails clearly.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** backend/apps/operations/cloud_jobs/task_sources.py

### D-135a — Shop modules and checkout rules
- **Area:** modules
- **Date:** 29 October
- **Decision:** Every shop feature has its own per-space switch. The shop is its own top-level module (an approved exception to D-97), supports per-product tax class and HSN with tax-inclusive prices, pickup at the space and at its events (no shipping), holds of 15 minutes for online checkout and 48 hours for pay-at-desk, guest purchase through name, email and email code, and member prices reusing the discount rules plus a members-only flag.
- **Why:** The maintainer noted that some spaces may not need each feature.
- **Status:** current
- **Implemented in:** `backend/apps/shop`

### D-135b — Shop module answers (Q-S7 to Q-S20)
- **Area:** modules
- **Date:** 29 October
- **Decision:** The shop is its own optional `shop` module and every shop feature has its own per-space switch. Returns run as refund cases inside a per-space window (default 14 days) with staff choosing restock or write-off. Cash-up is per session (float, counted total, variance) and gets the two-person check. Shop products are separate from inventory, optionally drawing on a consumable stock pool. Lendable tools are never sold. A kit is its own stocked item with an optional bundle mode. Low stock creates a To-Buy draft (else a notification). Public stock shows labels by default, exact counts opt-in. Receipts use the shared financial-year series (80 mm, A4, email). There are no pre-orders or back-orders. Uncollected orders get reminders at 3 and 7 days, then staff cancel and open a refund case after 30 days. An optional per-order quantity limit exists. Event add-ons and shop merchandise are kept separate.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/shop/`

### D-129 — The shop is per makerspace
- **Area:** modules
- **Date:** 28 October
- **Decision:** Each space has its own shop switch, catalogue, stock, prices, payment rail, receipts and finance records, never shared across spaces, though the superadmin sees all.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/shop`

### D-128c — Modules, grants and the shop
- **Area:** modules
- **Date:** 28 October
- **Decision:** Switching a feature off keeps its data, and purge is a separate audited superadmin action. Maintenance, To-Buy, warranty and repairs live under each parent with separate switches. Space Managers may enable or disable modules, while installing limited or paid modules and purges stay superadmin-only. Settings grants are per person, except that the Inventory Manager can always change rental timing. Donations and sponsors live under finance, ID programmes live under membership (cards need membership and member accounts), and a shop was chosen for the earlier "something else" pick.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `docs/MODULES.md`, `backend/apps/shop`, `backend/apps/id_programmes`

### D-97 — Fold maintenance, procurement and warranty into parents
- **Area:** modules
- **Date:** 24 October
- **Decision:** Maintenance, procurement (To-Buy) and warranty stop being top-level module keys and become capabilities under their parent module, with repairs and technicians following the same pattern. A migration maps old module keys to the new capabilities so existing spaces keep them on. New features live under inventory, machines or bookings as capabilities, never as new top-level modules, unless the maintainer says otherwise.
- **Why:** Keeps the module list small and features next to what they serve.
- **Status:** current
- **Implemented in:** `backend/apps/maintenance`, `backend/apps/procurement`, `backend/apps/warranty`, `docs/MODULES.md`

### D-95 — Every feature has a per-space switch
- **Area:** modules
- **Date:** 24 October
- **Decision:** Every feature is a module or a two-level capability with its own per-space on/off switch, editable by the Space Manager and the control plane, with dependencies completed automatically. Each action is audited, money goes through the ledger, and a feature that is off leaves no UI and no API surface (404 or 403); turning it on never loses data.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `docs/MODULES.md`, `backend/apps/space_controls`

### D-87 — Module matrix ticking
- **Area:** modules
- **Date:** 23 October
- **Decision:** In the control-plane module page a feature can be ticked alone, which also ticks its parent module and that module's dependencies. Unticking a module unticks its features with a notice listing what was turned off, and nothing is silently re-ticked on save.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `docs/MODULES.md`
