---
title: Back up and restore the server
summary: Encrypted archives, the schedule, restore drills, and running a full restore on the server.
order: 30
keywords: backup, restore, encrypted archive, age key, drill, schedule, restore.sh, import backup, disaster recovery
---
## How backups are protected

Archives are encrypted to the platform's backup key. Keep the private half of that key off the server: whoever holds it can read every backup. One-space archives also use this server's own restore key.

## The schedule

In the console's **Backup & restore**, set the **Daily full backup**. Each space also gets a nightly backup.

## Restore drills

Space Works regularly restores a space's backup into a throwaway database to prove it works (by default each space every seven days). Failures are emailed to superadmins. Setting the interval to 0 turns drills off.

![Screenshot: backup keys, drills and notices in /control/](screenshot:op-drills)

## A full restore

1. The superadmin requests the restore in the console.
2. On the server, run `scripts/restore.sh` with the restore's ID. For an archive you downloaded, import it first with `scripts/import-backup.sh`.
3. Restore the database first, then stored files.

To pull one space out of a whole-platform archive, decrypt it away from the server and extract that space's restore point.

Keep `.env` backed up separately: without its keys, restored data can't be read.

> **Who can do this:** the host operator, with the platform superadmin for the in-app steps.
