---
title: Log machine use for an event
group: How-to guides
order: 265
summary: Tag a machine session or a service request as done for an event, let the area manager set or clear that tag, see machine use on the event page, and understand what "charge the event" does and does not do.
---

# Log machine use for an event

"I am printing this for the maker faire." SpaceWorks can record that a machine session or a machine service request was done **for an event**, so the event's organisers can see what the event used, and the area manager can report on it.

There is **no switch** for this. It is always available wherever Machines and Events are both on. Nothing changes for a member who never picks an event.

## What you need first

- The **Machines** and **Events** areas are on for the space.
- For the cost approval at the end: event charges are tracked (`charges.enabled` and `charges.events`, see [rates and fees](rate-cards-and-fees.md)).

## Who can pick an event

When starting a session or sending a job request, a member sees **This is for an event** only if they have events to pick. The list holds the open events of **this** space they may act for:

- a registered or attended participant (including a free crew place),
- an active member of a hackathon team in the event,
- approved crew,
- an organiser or event staff (anyone the event's own permissions admit, a Space Manager included).

Cancelled and completed events are never offered, and an event of another space is never accepted. Choosing one is optional.

## Where the tag is given

| Place | Who | What happens |
| --- | --- | --- |
| Start a machine session (the machine's QR page) | The member | Optional picker; recorded with the session. |
| Book a machine's time | The member | Optional picker on the booking form; recorded with the booking. |
| Request a job (any machine type) | The member | Optional picker on the confirm step; recorded with the request. |
| Staff start a session for a member | Staff | Optional; any open event of the space. |
| A device (adapter) session start | The adapter | The adapter may send `event_id`. It is linked only if the session's member is eligible; otherwise it is **ignored and the session still starts**. |
| Accepting or handling a request, session or job | The area manager | **Event** on the card: set, change or clear it. |

The area manager is a Space Manager, or a Machine Manager whose scope covers that machine or machine type. Every change is audited with the event before and after (`machine_event.linked`, `changed`, `cleared`). A member sees only the event on their own sessions and jobs.

A **machine-time booking** can carry the tag too: the member picks the event on the booking form (machine spaces only), and the area manager can set, change or clear it from the booking card. A room booking cannot. Separately, staff can still link a booking to an event from the event side (the workshop machines on the event page); that is unchanged.

## What the event's staff see

Open the event and look for **Machine use** on the overview: the sessions, jobs and machine bookings logged for the event, who, which machine type, minutes, consumables used (from the job's usage records), the member's charge and the organiser's decision, with totals. It is visible to people who manage the event's registrations.

Reports: **Machine use by event** (counts per event and machine type, scoped to the machines the viewer manages) and **Machine use for an event** (one event's rows, with names). The analytics view `machine_event_links` carries the same links for Metabase.

## Charging the cost to the event

When event charges are tracked, an **organiser** (someone who can edit the event's details) can **approve** charging a linked item's cost to the event, and withdraw that approval.

This is a **record, not a money movement**:

- The organiser's decision is saved with the amount the charge stood at. Nothing on the member's charge changes.
- Until staff settle the charge, the **member's own charge stands**, exactly as raised.
- SpaceWorks has no event account that can absorb a member's charge: the per-event budget is a figure to measure against and the reimbursement pools pay money out. So staff settle an approved charge through the ordinary ledger (record what the event paid as an offline settlement with its receipt, or waive it). Settled money is never edited.
- While an approval stands, the event link cannot be changed or cleared; withdraw the approval first.

## Check it worked

1. As a member who is registered for an event, start a session or send a job and pick the event.
2. Open the event: the item appears under **Machine use**.
3. As the area manager, open the card and clear or change the event; the audit log shows before and after.
