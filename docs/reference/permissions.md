---
title: Roles and permissions
group: Reference
order: 30
summary: The fixed staff roles, the actions each holds, how roles combine and the rules that keep scopes apart.
---

# Roles and permissions

Access in SpaceWorks is **action-based and scoped to a space**. A person's account holds one or more roles in a space; each role grants a set of **actions**; every request is checked against those actions for that space. The platform **superadmin** is a separate, global account.

The role list is a fixed catalogue: you can grant, combine and revoke roles but not create or edit them. Machine Manager and Technician reach is assigned per person by machine type and/or individual machine.

## Roles

| Role | Can combine | Stored actions |
| --- | --- | --- |
| Space Manager | No | `accept_request`, `assign_box`, `edit_inventory`, `issue_direct_loan`, `issue_request`, `manage_bookings`, `manage_events`, `manage_devices`, `manage_machines`, `manage_makerspace`, `manage_members`, `manage_member_cards`, `manage_printing`, `manage_qr`, `record_payment`, `record_reimbursement_payout`, `reject_request`, `return_request`, `upload_evidence`, `view_audit`, `view_finance`, `view_inventory` |
| Inventory Manager | Yes | `accept_request`, `assign_box`, `edit_inventory`, `issue_direct_loan`, `issue_request`, `manage_qr`, `reject_request`, `return_request`, `upload_evidence`, `view_audit`, `view_inventory` |
| Machine Manager | Yes | `manage_machines` |
| Event Manager | Yes | `manage_events` |
| Booking Manager | Yes | `manage_bookings` |
| Handover | Yes | `view_inventory`, `assign_box`, `issue_request`, `issue_direct_loan`, `return_request`, `upload_evidence`, `collect_service_request` |
| Technician | Yes | `work_repairs`, `run_maintenance`, `set_service_state` |
| Shop Manager | Yes | `manage_shop`, `sell_shop`, `view_shop` |
| Fundraising | Yes | `manage_donations` |
| Member | No | none |

Some actions imply others: `manage_machines` implies `manage_printing` and `collect_service_request`; `manage_members` implies `manage_member_cards`, which implies `scan_member_cards`; `manage_shop` implies `sell_shop` and `view_shop`; and `manage_makerspace` (the Space Manager) implies ID-programme management, card design approval, the shop, analytics and donations.

## What the actions mean

| Action | Lets the holder |
| --- | --- |
| `view_inventory`, `edit_inventory` | Read, or change, the catalogue and stock |
| `accept_request`, `reject_request` | Decide a reviewed hardware request |
| `assign_box`, `issue_request`, `return_request` | Hand out and take back hardware (issue needs a box scan and issue photo; return needs a return photo and remark) |
| `issue_direct_loan` | Hand out with no reviewed request, with the same evidence |
| `upload_evidence` | Upload issue and return photos |
| `manage_qr` | Generate, resolve and revoke QR codes |
| `collect_service_request` | Hand a finished machine job to its requester |
| `manage_machines`, `manage_printing` | The machine lifecycle and the print and service queue |
| `manage_events`, `manage_bookings` | Run events or bookings |
| `scan_member_cards`, `manage_member_cards` | Resolve a card to minimal identity; issue, reissue, revoke and print cards |
| `manage_members` | The member roster |
| `manage_devices` | Enrol and revoke printers and label printers |
| `view_finance`, `record_payment`, `record_reimbursement_payout` | Money: read the ledger, take a payment, record a payout |
| `view_audit` | Read audit entries within the holder's area |
| `work_repairs`, `run_maintenance`, `set_service_state` | Technician work within their coverage |
| `manage_shop`, `sell_shop`, `view_shop` | Shop catalogue and settings; selling and handing over orders; reading orders and stock |
| `manage_donations` | Donations, sponsors, donor list and receipts |
| `view_id_programmes`, `manage_id_programmes`, `approve_card_designs` | Organization ID programmes and card design approval |
| `view_analytics` | Open the space's embedded analytics dashboards |
| `manage_makerspace`, `manage_staff`, `transfer_stock` | Space settings and staff; reserved for the Space Manager or superadmin |

## Rules that keep scopes apart

- **Only the Space Manager holds money, staff, member roster, device or settings authority.** No area role gains `view_finance`, `record_payment`, `manage_makerspace` or `manage_members`. Area money stays scoped to its area.
- **Area roles do not cross.** Event, Booking, Machine, Technician and Shop roles hold no lending action; Handover holds no decisions, catalogue or QR administration. Combine roles to give a person both.
- **Handover is a narrow console.** A person holding only Handover sees the counter screens.
- **Audit is per area.** The Inventory Manager reads lending, handover and inventory-repair entries only; only the Space Manager and superadmin read the whole space. Machine, Event, Booking and Shop Managers and the Technician read their own area's audit entries.
- **Evidence rules do not relax for any role**: issuing needs a box scan and an issue photo; returning needs a return photo and a remark.
- **Payee and payout money is session-only.** Tokens, app connections and API clients cannot read it (`full_session_required`).
- **Staff must have two-step sign-in** (three-day grace for new staff).

## Other kinds of authority

| Who | Scope |
| --- | --- |
| Platform superadmin | Global, via the platform console and `/control/` |
| Organization members | Authority derived from an organization, never across spaces the organization is merely linked to |
| Event helper roles | Volunteers, mentors, judges and sponsor reps invited to one event, with that helper role's permissions |
| Resource grants | Staff granted a specific booking resource or event |

## See also

- [Give someone a role](../how-to/roles-and-handover.md)
- [Role and finance access](../RBAC-MEMBERS-FINANCE.md)
- [Invariants: handover roles and the per-role matrix](../INVARIANTS.md)
