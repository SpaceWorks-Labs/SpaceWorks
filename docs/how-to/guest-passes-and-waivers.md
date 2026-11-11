---
title: Set up guest passes and waivers
group: How-to guides
order: 160
summary: Let non-members visit on a dated pass, choose what a pass unlocks, require a waiver and sell day passes.
---

# Set up guest passes and waivers

A **guest pass** is a dated permit for someone who is not a member. It is sponsored by a member, issued by staff, linked to an event registration, or bought as a day pass. A pass is never a membership: it is not on the roster and carries no member benefits.

## Before you start

- **Membership** is on.
- You are the Space Manager.
- Switch on **Guest passes** (`membership.guest_passes`) in **Settings > Areas > Features**. For paid passes also switch on **Day passes** (`membership.day_passes`).

## Set the rules

Open **Settings > People > Guest passes**. Live passes keep the rules they were issued with; changes apply to new passes.

| Setting | What it decides |
| --- | --- |
| Guest borrowing | Whether guests can borrow, on site only (items are due back by the end of the pass; full borrowing always takes a deposit) |
| Guest machine use | **Supervised** (only inside a certified instructor's session) or **after induction** (a certification granted at an induction event) |
| Who pays for a sponsored guest's lost or damaged items | The guest, or the sponsoring member. Either way the sponsor is told |
| Walk-in and door registration creates | A guest pass for the day, or a full membership |
| Waiver before a guest is on site | Guests accept the current waiver on their phone or at the desk before check-in |
| Sponsoring members | The member must be checked in; days of membership first; guests per member at once |
| Visits and joining | Visits before the join prompt, an optional visit limit, and day passes per day |

## Waivers

1. Turn on **Require the waiver** so guests accept the current waiver before they are on site.
2. Optionally tick **Keep asking for the waiver if guest passes are switched off** so non-members still sign one at check-in even without passes.
3. A guest accepts from **My passes** before arriving, or at the desk. The pass records the waiver version they accepted, and a pass can be revoked at any time: a revoked, expired or converted pass stops working at once, even if a copy sits in someone's wallet.

> **Note** Waivers are liability evidence. They stay even if guest passes or membership are switched off.

## Sell day passes

With `membership.day_passes` on, a guest can buy a one-day pass, or staff can sell one at the desk. The price is recorded as money owed under the membership charges and is payable online only when online payments are on. Staff may waive it. A paid day pass gives no joining credit.

## Issue a pass at the desk

Staff manage passes under **Members**, **Guests**: issue or sell a pass, check (scan) one and revoke it. Scanning a pass resolves it against the live record on the server.

## See also

- [Add wallet passes](wallet-passes.md) to let guests keep a pass in their wallet.
- [Minors and guardian consent](minors-and-guardian-consent.md)
- [Module guide](../MODULES.md) (`membership.guest_passes`)
