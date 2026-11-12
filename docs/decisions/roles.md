# Decisions: Roles and access

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-282 — Fixed roles, multiple roles and per-machine scope
- **Area:** roles
- **Date:** 11 November
- **Decision:** There are no custom roles; the nine fixed roles stay. A staff member may hold several roles at once, and every view, dashboard, notification and report shows the union of what they hold. Machine scope can be set per machine type and per individual machine (union of both; nothing listed means nothing) for Machine Manager and Technician, on grants, invitations and acceptance, with same-space validation and an audit row on every change.
- **Why:** Combining roles covers delegation needs (for example Events Manager plus Bookings Manager) without custom roles.
- **Status:** current

### D-248 — Member 360 counts, bulk endpoints and missing area reports
- **Area:** roles
- **Date:** 10 November
- **Decision:** Member 360 counts are visible to every staff role holding an area action in the space (rows stay limited to managed areas). Bulk endpoints are all-or-nothing (at most 50 items, 409 with the failing id). Area owners' cash refunds have no maker-checker step because the refund path has none. Bulk staff invites, bulk plan assignment, the missing area reports/exports and remaining list filters were added.
- **Why:** Matches the area-action scoping model; keeps bulk operations predictable. Remaining detail not recorded.
- **Status:** current

### D-242 — Role completeness, money workflows, donations
- **Area:** roles
- **Date:** 10 Nov 2026
- **Decision:** Each charge's subject owner may record an offline payment and waive, exposed on every charge type plus an own-area Payments queue, with no new `record_payment` grant; "I paid" claims, pay links and reminders are handled by the charge owner and cash refunds by the area's manager. Rate cards show inside each area, editable only when the Space Manager delegates. Staff Member 360 shows counts for every area and rows only for managed areas. Technicians read incidents on covered machine types, and the Event Manager sees an event's loans and guest passes read-only. A single staff Schedule page shows each role's own layers. The superadmin gets a cross-space queues table, per-space counts, unread inbox and platform search (superadmin-only, audited, rate-limited). Donations need a non-profit profile (registration and tax-exemption IDs) to issue tax receipts; the Space Manager runs donations and donation money is never shown to area managers.
- **Why:** ROLE-COMPLETENESS-AUDIT-0.12.0.
- **Status:** current

### D-241 — Area managers see a complete view of their own area
- **Area:** roles
- **Date:** 10 Nov 2026
- **Decision:** Area managers get area-scoped Finance, To-Buy, consumables, repairs, warranties, reports, audit and notifications for their area, with machines grouped by type then machine and inventory by category. The Space Manager sees the same views combined, grouped by area with per-group totals, collapsible groups and an area filter. Server scoping per D-224 stays authoritative.
- **Why:** Reason not recorded
- **Status:** current

### D-224 — Each role sees only what it manages, enforced at the API
- **Area:** roles
- **Date:** 10 Nov 2026
- **Decision:** Reports are keyed to their own area: machine health and printer-service money need `MANAGE_MACHINES`, member activity, growth, engagement, join-funnel and accountability need `MANAGE_MEMBERS`, and `view_audit` alone no longer opens another area's report. Linking an event as an induction also requires authority on that event. Payee/payout money is session-only everywhere. Handout-only roles get a counter-only API with inventory-wide reports and exports refused. An audit fixed 13 API leaks (feeds, live streams, report schedules, dry-run bands, induction attendees, draft event offers and others).
- **Why:** API role-scoping and role-screen audits.
- **Status:** current
- **Implemented in:** docs/INVARIANTS.md

### D-217 — Per-role access matrix
- **Area:** roles
- **Date:** 9 Nov 2026
- **Decision:** The nine fixed built-in roles keep their stored grants. Only the Space Manager holds money, roster, device and settings authority; area money stays domain-scoped and refund/settlement authority stays with each charge's subject owner. Widenings rejected: no `view_inventory` for Event/Booking Managers, no member-card scanning for Inventory Manager or Handover, no `record_payment` or shop selling for Handover. The console is aligned to what the server already serves (Reports, Finance and Refunds open to the relevant area roles), and each role lands on its own dashboard or first permitted tab.
- **Why:** Least privilege and separation of duties; each job need is already met through domain scoping, implied actions or resource grants.
- **Status:** partly superseded by D-219
- **Implemented in:** backend/tests/fixed_roles/test_role_access_matrix.py, frontend/src/features/staff/staffAccess.roleMatrix.test.ts, docs/INVARIANTS.md

### D-195 — Superadmin acts in paused and read-only spaces
- **Area:** roles
- **Date:** 5 November
- **Decision:** The superadmin may write in a paused or read-only space, audited with `bypass_space_control=<state>` and with a visible warning; everyone else stays refused through the single write-policy guard. Queued messages are held, not dropped, and reminders run at 30/7/1 days.
- **Why:** Follows D-190, nothing is switched off for the superadmin.
- **Status:** current
- **Implemented in:** `backend/apps/space_controls/`

### D-190 — Superadmin is never switched off; web console parity
- **Area:** roles
- **Date:** 5 November
- **Decision:** Every feature, module screen, report and setting in every space stays reachable by the superadmin, and the web superadmin console offers every day-to-day platform operation, since `/control/` is the server-side power tool. Only actions needing host access by design (platform key rotation, whole-platform restore, recovery commands) stay server-side. A test pins every `/control/` action to a web path or a host-only list.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/config/control_parity.py`

### D-137 — Shop Manager scope and other open answers
- **Area:** roles
- **Date:** 29 October
- **Decision:** Shop Manager covers products, stock, prices, orders, POS, cash-ups, returns, shop reports and the shop's own settings without a grant, and nothing else. Default roles are now the seven existing ones plus Technician and Shop Manager (nine). A Technician works assigned jobs and maintenance within its role's machine types, sees only the reporter's first name and may record parts used (through availability, audited). Staff and member login data travel on a space move (password hashes, TOTP, recovery codes; passkeys only on the same domain; never sessions or devices). Venue fees mean a space charging an outside organiser. Leader-pays team registration uses one fixed price per team.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/shop/`, `backend/apps/accounts/rbac.py`

### D-135c — Shop Manager role and shop money visibility (Q-S9, Q-S10)
- **Area:** roles
- **Date:** 29 October
- **Decision:** A built-in Shop Manager role sells, refunds and cashes up; the Space Manager can too, and nobody else unless granted. Shop money is visible to the Space Manager and Shop Manager (plus the finance-view action per the ledger rules). See D-137 for the role's full scope.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/shop/`

### D-128b — Technician role, notifications and quotes
- **Area:** roles
- **Date:** 28 October
- **Decision:** A built-in Technician role sees and updates repair jobs assigned to it and runs scheduled maintenance, with no inventory editing, money or settings; outside contractors without accounts stay contacts. Notification is by email always, Telegram or WhatsApp after a one-time opt-in, and SMS if enabled. The area manager or Space Manager approves quotes with no threshold, and a room outage defaults to blocking new bookings with existing bookings listed for staff to cancel (full refund) or keep.
- **Why:** Reason not recorded.
- **Status:** current

### D-115 — Superadmin sees everything per space
- **Area:** roles
- **Date:** 27 October
- **Decision:** The superadmin can view and edit any space's email setup, send tests and read delivery logs (audited in that space), and can see analytics and reports through a space switcher, per-space links in the control plane and platform-wide comparison pages. A parity guard test proves every Space Manager surface is reachable by the superadmin for every space.
- **Why:** Reason not recorded.
- **Status:** current

### D-102 — Managers do maintenance in their scope
- **Area:** roles
- **Date:** 24 October
- **Decision:** Machine, Inventory and Booking managers can view and do maintenance and repairs in their own scope (schedules, logging, fixing, remarks, photos, parts, cost) and may act as the technician, with costs going to the ledger. Space Managers can do this everywhere.
- **Why:** Reason not recorded.
- **Status:** current

### D-101 — Settings authority and delegation
- **Area:** roles
- **Date:** 24 October
- **Decision:** The Space Manager controls every setting and can grant a module's manager full control of that module's settings per module; without a grant, module managers view but do not change. The Space Manager can revoke grants and lock individual settings, and every settings change is audited with who made it and under which grant.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/space_controls`

### D-63 — One account per person
- **Area:** roles
- **Date:** 21 October
- **Decision:** A person has one account, and staff roles are granted to an existing account (or an email invite creates it). The staff console appears when the account holds a staff role and MFA then becomes mandatory; the superadmin stays a separate platform account. The API takes a clean break from the old member/staff split.
- **Why:** Reason not recorded.
- **Status:** partly superseded by D-65
