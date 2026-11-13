---
title: Export your data
group: How-to guides
order: 100
summary: Request a readable copy of your space's records, and know how it differs from a backup.
---

# Export your data

A **data export** is a readable copy of your space's records. It is not a backup and cannot be restored into a server; for that use [backups](offsite-backups.md) or a [space move](move-a-space.md).

## Request an export

1. Open **Data export** (`/admin/data-export`). Space Managers see it under **Settings > Administration**.
2. Press **Request export**. Only one export can be building at a time.
3. Watch the status: **Queued**, **Building snapshot**, then **Ready**. A failed export shows why; one that took too long can be retried at a quieter time.
4. Press **Download** on a ready export. The download link is prepared when you press the button and is short-lived.

## What is in it

The archive includes the records your space owns. It leaves out credentials, bearer tokens, platform configuration, selected JSON configuration, audit metadata and free-text form answers.

> **Warning** The export **does** contain member contact details: names, email addresses and phone numbers in readable form. A small referenced-users file lists the id and username of people referenced by exported rows. Handle the file like any personal data.

## Reports and smaller exports

Many screens have their own CSV download (event registrations, booking reservations, equipment and consumables reports, guest lists, platform overview). Those exports are recorded in the audit log where the screen says so. Reports that include payout amounts can only be read in an interactive session, not through tokens or API clients.

## A member's own export

Members can export their own data from their account (see [Account portability](../account-portability.md)). A deleted account follows the retention rules in [Privacy and account deletion](../privacy-account-deletion.md).

## See also

- [Back up and restore](offsite-backups.md)
- [Move a space to another server](move-a-space.md)
