---
title: What Space Works is
group: Getting started
order: 10
summary: What Space Works does, who it is for, and the ideas that make it different.
---
# What Space Works is

Space Works is free, open-source software (AGPL-3.0-or-later) for running a makerspace, fab lab, school workshop or any community that shares equipment. It answers the everyday questions a space has to answer: what do we own, who has it, is it available, who is allowed to use this machine, what is on this week, and who owes what.

The central idea is **traceability of physical handovers**. Every time hardware leaves or comes back, Space Works records evidence: a QR scan, a photo, a remark and an audit entry. Tools stay tied to people, and a disagreement about "who had the drill last" has a factual answer.

## Who it is for

| You are | What Space Works gives you |
| --- | --- |
| A **makerspace organiser** | One place for inventory, loans, machines, events, bookings, memberships and money, with a trail behind every handover. |
| A **member or visitor** | A public catalogue to browse, requests to borrow, event and booking pages, and a member area with your own history. |
| **Staff** (inventory, machines, events, bookings, front desk, shop, technician) | A console that shows only the area you manage. |
| A **network, university or chain** | Many spaces on one deployment, plus organizations that reach across them. |
| A **self-hoster or contributor** | Docker-based install, documented environment, an OpenAPI-described API and a modular code base. |

## What it covers

Space Works is built from **modules** you switch on only when you need them. See [choosing modules](../choosing-modules.md) and the [module reference](../MODULES.md) for the full list. In broad strokes:

- **Inventory and loans**: items, QR-tracked units, containers and kits, requests, handover, returns, stocktake, consumables.
- **Machines**: job requests, quotes, queues, sessions, certifications, maintenance and repairs.
- **Events and bookings**: public event pages, tickets, registration, check-in, bookable rooms and resources.
- **Membership and money**: plans, renewals, member cards, charges, receipts, and an optional online payment rail.
- **Communication**: email, chat rooms (Telegram, Slack, Discord, Mattermost), SMS and WhatsApp, push and webhooks.
- **Reports and analytics**: built-in reports plus read-only database access for Metabase or Grafana.

## Ideas worth knowing before you start

- **Evidence is not optional.** Hardware cannot be issued without a box scan and an issue photo, and cannot be returned without a return photo and a remark. See [the request lifecycle](../architecture/request-lifecycle.md).
- **Everything is scoped to a makerspace.** One deployment can host many spaces and none can see another's data. See [tenancy and roles](../architecture/tenancy-and-roles.md).
- **Access follows actions, not titles.** Roles are bundles of actions; a person gets only what their role grants.
- **Your data stays with you.** Self-hosting keeps members' data in your own database. See [data and privacy](../architecture/data-and-privacy.md).
- **Two rules keep the system honest.** One workflow module owns every request state change, and one availability module owns every quantity count. See [modules](../architecture/modules.md).

## Where to go next

1. [Getting started](getting-started.md): install, first-run setup and your first loan.
2. [Glossary](glossary.md): the words used throughout the app and these docs.
3. [FAQ and troubleshooting](faq.md).
4. [Choose your hosting](../choose-your-hosting.md) if you have not decided where to run it.
