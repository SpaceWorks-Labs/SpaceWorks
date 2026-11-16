---
title: Give members machine access
group: How-to guides
order: 255
summary: Decide who may use each machine by granting access to members, with an optional end date, and what happened to certifications.
---

# Give members machine access

From 0.12.0 SpaceWorks has **no certifications or inductions**. Who may use a machine is decided by the people who run
it: the Space Manager (and a Machine Manager for the machines they look after) grants access to whoever they choose.
There is no course, test or training record behind it.

## How access works

- A **grant** names one member and either one machine or every machine of one machine type. It can have an end date
  and a note. It is never edited away: it can be renewed or revoked, and every grant, renewal and revoke is audited.
- A machine can also be marked **Open to all members**. Any active member may then use it with no grant. It is off by
  default for new machines. Guests do not benefit from this setting; a guest needs their own grant.
- The access rule is only the first question. Standing, check-in, bookings, maintenance lockouts and supervision
  are still checked, as before.
- A supervised session still works for someone with no access: the instructor takes them onto the machine inside the
  session, and no grant is needed.

## Who can grant

The same people who already manage that machine: the Space Manager for everything, a Machine Manager only for the
machine types and machines linked to them. There is no new permission to assign.

## Give access

1. Open **Machines**, then **Machine access**, and choose **Give access**.
2. Pick the machine or the machine type, then one or more members. Set an end date if you want one, and add a note.
3. Save. Each member is told, and is told again a week before an end date.

Other places to do the same thing: the **Machine access** tab on a machine type or machine (including **Open to all
members**), a member's own page, and the member register (select members, then give machine access; this needs the
Machines module and machine authority).

To remove access, revoke the grant. The member is told.

## What members see

**Profile and card, My machine access** lists the machines and machine types they may use, when each ends, and the
machines open to everyone. Members never see the staff note.

## When someone is refused

Starting a machine session, requesting a machine job, booking a machine, linking a machine booking to an event, a guest
pass that unlocks machines, and a device adapter's access decision all use the same rule. The refusal reasons are:

| Reason | Meaning |
|---|---|
| `no_machine_access` | The member has no grant for the machine or its type, and the machine is not open to all members. |
| `machine_access_expired` | They had a grant and its end date has passed. |

Device adapters receive these as the `reason` of a denied `access.authorize`; see [Device Adapter API](../device-adapters/api.md).

## What happened to certifications on upgrade

Migration `machines.0040_certifications_to_access_grants` ran once and changed no certification record:

- In a space that had certification gating on, a member who held a live certification for **every** required machine type
  gets a grant for that type, ending when their earliest certification would have.
- Machines whose type was not gated, or in a space that never turned gating on, become **Open to all members**, so nobody
  loses access.
- Live guest certifications become grants.

Certification records are kept read-only (in `/control/` and in data export). The certification screens, induction
events, grant and training-note lists, and the booking and event override fields are gone, and their old routes answer
`410`. The three certification switches stay registered but always read off. Event certificates are unaffected.

## Check it worked

- A member with a grant can start a session; one without is refused with `no_machine_access`.
- After the end date the refusal reads `machine_access_expired`.
- The audit log shows `machine_access.granted`, `machine_access.revoked` and `machine.open_access_changed`.

## See also

[Machines](../modules/machines.md#machine-access-replaces-certifications) and
[Give someone a role](roles-and-handover.md).
