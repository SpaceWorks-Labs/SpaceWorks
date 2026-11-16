---
title: Platform backups and restores
summary: Back up one space or the whole platform, set the schedule, and restore with a preview.
order: 80
keywords: backup, restore, deployment archive, whole platform, disaster recovery, roll back, schedule, restore point
---
## Choose the scope

Open **Backup & restore**. Under **What to back up or restore**, choose **Whole platform** or one space.

## One space

1. Press **Back up now**, or pick a restore point.
2. Press **Restore…**, review the **Preview**, type the space's short name and confirm with your password.
3. Watch **Restore progress**.

A safety backup of the space is taken first.

## The whole platform

1. Press **Create full deployment archive** for a backup now.
2. Set **Daily full backup** and how long to keep on-demand archives.
3. To restore, press **Restore from a backup…**, choose the archive, and choose **Roll back in place** or **Disaster recovery**.
4. Type `deployment` and press **Review restore**. Read the report of every table before you go ahead.

![Screenshot: Backup & restore with the whole-platform scope](screenshot:sa-backups)

A whole-platform restore replaces live data, and the final step runs on the server. See [Back up and restore the server](help:host-operator/backups).

> **Who can do this:** the platform superadmin; the host operator runs the server side of a full restore.
