# Member and finance delegation (F6)

Membership roles are fixed and local to one makerspace: Space Manager, Inventory Manager, Machine
Manager, Event Manager, Booking Manager, Handover and Member. Space Manager and Member stand alone;
the other five combine freely. There is no custom-role editor or editable grant list. The action
checks below remain the authorization contract, including organization-derived grants. See
[roles and access](README-HOSTING.md#roles--access) for assignment and machine-type scope.

| Action | Grants |
| --- | --- |
| `manage_members` | Roster and request queues, community invitations and approvals, verification/referral delegation, witnessed waiver acceptance, plan reads and term assignment/cancellation. Implies `manage_member_cards`, which implies `scan_member_cards`. |
| `view_finance` | Full payment ledger, settlement receipts, payment reconciliation report and exports. Does not grant cash recording, waivers or refunds. |
| `record_payment` | Offline settlements, receipt corrections, and offline refund receipts across the makerspace's charge subjects. Does not grant settings, debt waivers or online refunds. |

Space Manager includes `manage_members`, `view_finance` and `record_payment`. There are no separate
Membership Coordinator, Treasurer or front-desk cashier built-ins; old custom roles are mapped by
migration 0089's raw-grant subset rules and can lose authority that no built-in represents.
Handover includes job collection and evidence but does not independently grant cash recording.
Machine Manager reach is assigned per person by type; combining roles unions actions without
widening that machine reach.

Actors holding only `manage_members` (for example via organization authority) may assign only Member
and cannot replace staff grants. Staff account provisioning and role-set changes, makerspace
settings, membership plan definitions/prices and waiver publishing require `manage_makerspace`.
Membership-only roster responses do not include payment summaries. Community-only actors cannot
approve or cancel staff invitations by substituting a community role. Verification and term controls
remain available on staff roster rows; changing/revoking staff roles requires makerspace administration.

The roster uses `view_finance` for money visibility, `record_payment` for cash recording,
and the existing membership-subject authority for waiving a debt. A read-only finance
grant shows amounts without payment mutation controls. The report console uses the same
finance grant to render money reports without loading unauthorized hardware summaries.

The full payment list requires `view_finance`. A cashier uses the same route with
`for_recording=true`: it requires `record_payment` and returns pending and offline-settled
charges needed for receipt work. The query cache distinguishes these scopes. Money
reports still require `view_finance`. The ledger and cash recording work with the online
`payments` module off; the `reports` and `membership` module gates remain unchanged.

Existing charge-domain staff retain their scoped cash recording paths. Debt waivers and
online refunds retain their existing subject authority and machine scoping. Finance
authority never implies machine lifecycle authority.

Historically `makerspaces.0078_member_finance_actions` backfilled the three actions onto roles and
organization memberships holding `manage_makerspace`. Fixed-role migration 0089 replaces editable
local grants with the canonical catalogue; organization reach, hidden-space fences and the legacy
null-primary fallback remain unchanged. `manage_makerspace` does not dynamically imply those actions.
The old additive migration has a no-op reverse; the fixed-role data migration is irreversible.
Operators must back up, stop writers and run `python manage.py preview_fixed_roles` with the new
image before `migrate`; resolve every “must fix before upgrading” notification rule first. See
[upgrade recovery](update-recovery.md#fixed-role-upgrade-2026-10-16).

All routes continue to use the central RBAC makerspace scope, active-account checks,
tenant-origin restrictions and superadmin-hidden fences. Cash and membership mutations
retain their transaction and audit services. No model, module or feature key was added.
