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

## How staff management works

- **One account, many roles.** Nobody has a separate "staff account". A person has one SpaceWorks account, and a staff role is a grant on that account for one space. The same person can be a member in one space, Inventory Manager in a second and Event Manager in a third, all with one sign-in.
- **Roles combine.** Everything except Space Manager and Member can be held together, and the person sees the union of what the roles allow.
- **Machine reach is per person.** A Machine Manager or Technician covers the machine **types** and/or **individual machines** you choose for that person. A type covers every machine of that type, including ones added later; with nothing picked they see no machines.
- **Only members can be granted directly.** To give someone a role who has no membership in the space, invite them by email.
- **Only the platform administrator handles the Space Manager role.** A Space Manager can manage every other staff row, but cannot grant, change or revoke a Space Manager. Nobody can change their own staff row, and the last active Space Manager cannot be revoked.

### Invitations

An email invitation records the address, the roles and the machine scope you chose. The link goes only to the invited address (and to their own chat channels if that address belongs to a verified account); staff rooms hear only that an invitation was sent. The person accepts it while signed in with a fresh emailed code, and it creates no account by itself. **Invitations** lists pending ones, which you can resend or revoke.

### What revoking a role does

- The role ends and the person loses that space's staff access straight away, including any device grants issued for that space's staff tools.
- Their **account, their membership and their history stay**. They can still borrow, book and use the member area, and everything they did while staff stays in the audit log.
- A revoked role can be **restored** later.
- If they held a **staff ID card**, it ends with the role (see below). Changing roles reissues it with the same number and a new QR.
- The grant, change, revoke and restore are all audited, and the person gets a private notice when a role is granted or restored.

To turn off a whole account everywhere, the platform administrator uses "Disable account" in the control plane; that revokes every session and every staff role at once.

### Staff ID cards

With **Staff ID cards** switched on (Memberships area), each active staff member can hold one ID card showing their name, photo and every role they hold, and for Machine Managers and Technicians the machine types and machines they look after. It has its own numbering (`STF-0001` by default) and design, and a public check page that shows only the name, "Staff" and valid or revoked, never contact details. The card ends by itself when the staff access ends, and can be issued automatically when a role is granted. Staff see their own card under **My cards**. See [Memberships](../modules/memberships.md) for numbering, design and printing.

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
- [Staff ID cards in Memberships](../modules/memberships.md)
