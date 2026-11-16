---
title: Space health, service pauses and closure
summary: Inspect a space, pause service, transfer ownership, or schedule archive and deletion.
order: 35
keywords: spaces, health, suspend, unblock, read-only, archive, purge, transfer, announcements, onboarding
---
Open **Spaces** in the platform console. Under **Health**, find the space and open its **Manage** menu. Use **Details** to review its state and **Open console** to enter an active space.

## Pause or resume service

- **Suspend** pauses ordinary service. Give the reason in the confirmation dialog. Use **Unblock** to restore service when it is safe.
- **Make read-only** blocks ordinary changes while permitted reads remain available. **Lift read-only** removes the manual restriction. Other restrictions, such as an import or expired managed plan, keep their own rules.
- **Transfer ownership** changes who is responsible for the space. Review the recipient and confirm your identity when asked.

## Archive and purge

1. Choose **Schedule archive & purge** for a future closure, or **Archive now** for immediate archival.
2. For a schedule, review **Archive on**, the grace period and the exact space slug before confirming.
3. Use **Cancel schedule** while the schedule is still active to stop the planned actions.
4. An archived space offers **Unarchive**, **Schedule purge** and **Purge**. Purging permanently removes the space's data. Review the confirmation and type the exact slug.

Archive retains the space's records and pauses service. A scheduled purge is a separate permanent step. Export what you need before its due date. Current state, dependencies and confirmation checks can prevent an action.

## Onboarding and announcements

Use **Onboarding** for incoming hosting requests. Use **Announcements** to create staff banners for selected spaces or the whole platform, with member visibility where offered. Set the intended audience and active period before saving.

**Health** also shows usage, backups, the latest restore drill, security counts, open issues and managers. Use **Keys** or **Capability data** from **Manage** for those separate operations.

> **Who can do this:** the platform superadmin.

![Screenshot: the platform Spaces Health list and its Manage menu](screenshot:superadmin-space-lifecycle)
