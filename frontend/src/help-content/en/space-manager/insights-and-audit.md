---
title: Reports, saved views and the audit log
summary: Run and schedule reports, save the views you use, and look up who did what.
order: 95
keywords: reports, analytics, export, csv, xlsx, schedule, saved views, audit log, history, who did what
actions: view_audit, view_finance, manage_machines, manage_events, manage_bookings, manage_printing
---
## Run a report

1. Open **Reports** and **Choose a report**.
2. Pick a **Date range**: 7 days, 30 days, a quarter, or your own dates.
3. Press **Export CSV** or **Export XLSX** to download it.

![Screenshot: the Reports page with a chosen report](screenshot:sm-reports)

Each person sees only the reports their role allows, narrowed to their area.

## Schedule a report

1. Press **Schedule…**.
2. Choose the report, how often, the format and who receives it. Press **Create schedule**.
3. Use **Run now**, **Pause** or **Resume** on an existing schedule.

Recipients must also be allowed to open that report.

## Save a view

Open **Views**, press **Save current view…**, name it and press **Save view**. Use **Share to makerspace** to give it to your team.

## The audit log

1. Open **Audit log**. It lists every change in your space; nothing in it can be edited or deleted.
2. Filter by action, person, what changed, or date.
3. Open an entry for its details.
4. Press **Verify these entries** to check nothing has been tampered with.

## Web telemetry

With the Analytics module on, open **Reports → Analytics → Web telemetry**. Choose one page
analytics provider and enter its public site or measurement ID; choose `none` to turn it off.
Umami needs its website UUID and an endpoint approved by your operator. Session replay and
diagnostics are separate choices. Replay is limited to the anonymous public `/about` page. All collection requires the visitor's consent, and private or
unknown pages are excluded. Do not paste a server secret into these public settings. Ask your
operator to approve destinations and verify privacy controls before enabling a provider.

Firebase browser notifications use a separate notification opt-in and service-account setup;
enabling analytics does not enable alerts. Your operator can explain the setup and limits.

> **Who can do this:** reports follow each person's area (finance, audit, machines, events, bookings). The audit log needs the audit action, held by the Space Manager and Inventory Managers.
