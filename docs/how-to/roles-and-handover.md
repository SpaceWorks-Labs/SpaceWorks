---
title: Give someone a role
group: How-to guides
order: 80
summary: Invite or grant the built-in staff roles, combine them, scope Machine Managers and Technicians, and set up a front-desk Handover role.
---

# Give someone a role

Roles are granted to a person's own account; there are no separate staff accounts. The role list is a **fixed catalogue** of built-in roles: you grant and combine them, and you cannot create or edit roles.

> **Warning** If you are upgrading from 0.9.x, the one-way fixed-role conversion maps old roles to these built-ins. Read the [fixed-role upgrade](../update-recovery.md#fixed-role-upgrade-2026-10-16) first.

## The built-in roles

| Role | Holds | Can combine |
| --- | --- | --- |
| Space Manager | Everything in the space, including money, staff and settings | No, stands alone |
| Inventory Manager | Lending decisions, issuing, returns, inventory editing, QR, audit for lending | Yes |
| Machine Manager | Machines (per machine type and/or machine, set per person) | Yes |
| Event Manager | Events | Yes |
| Booking Manager | Bookings | Yes |
| Handover | The front desk: view inventory, assign a box, issue a request, issue a direct loan, take a return, upload evidence, collect a finished machine job | Yes |
| Technician | Work assigned repairs, run maintenance, set service state | Yes |
| Shop Manager | The shop: products, stock, orders, front desk, reports | Yes |
| Fundraising | Donations and sponsors only | Yes |
| Member | A plain member | No |

The full action matrix is in [Roles and permissions](../reference/permissions.md).

## Grant a role

1. Open **Staff & roles** (`/admin/users`) and press **Add staff**.
2. Pick a member of this space, or choose **Invite several by email** for people without an account. Invitations are accepted while signed in, with a fresh emailed code.
3. Tick the roles. Everything except Space Manager and Member can be combined.
4. For a Machine Manager (and a Technician), choose the machine types and/or individual machines they cover. Coverage is set per person, and a type covers every machine of that type, including ones added later. In the role editor a person can hold several roles at once, for example Machine Manager plus Technician.
5. Save. The change is audited.

## Set up a handover desk

The Handover role is the narrow counter console: it issues accepted requests, creates direct handouts, processes returns and uploads evidence, and nothing else. It cannot accept or reject requests, edit inventory or manage QR codes.

1. Make sure the **Inventory** area is on (**Areas & add-ons**).
2. Grant the **Handover** role to desk staff. A person who holds only this role sees the narrow console.
3. If the same person also reviews requests, give them **Inventory Manager** too; combining roles is how a person gets both.

Evidence rules do not relax for the desk: an issue still needs a box scan or a selected tool and an issue photo, and a return still needs a return photo and a remark.

## Check the result

- **Staff & roles** has a role filter ("Nobody here holds that role" means exactly that) and a read-only role reference.
- From the server, `python manage.py staff_mfa_readiness` lists new staff who still need a second factor.

## See also

- [Roles and permissions](../reference/permissions.md)
- [Role and finance access](../RBAC-MEMBERS-FINANCE.md)
