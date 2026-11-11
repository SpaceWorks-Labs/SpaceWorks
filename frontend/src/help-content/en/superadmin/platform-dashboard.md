---
title: The platform dashboard
summary: Every space at a glance: problems, usage, scheduler health, backups and analytics.
order: 30
keywords: platform dashboard, problems, checks, usage, limits, scheduler, analytics, backup status, health
---
1. Open **Platform dashboard**.
2. Read the space counts and the delivery and usage totals.
3. Check **Problems**: each check shows OK, warning or error. Press **Inspect** on any item.
4. Press **Run checks now** to check again. Checks also run every 15 minutes on their own.
5. Review **Makerspace usage**, **Scheduler freshness** and **Analytics** to compare spaces.
6. The **Backup status** rail links to the backup settings.

![Screenshot: the Platform dashboard with Problems](screenshot:sa-dashboard)

**Usage & limits** shows each space's usage against its plan on a hosted platform. Look into any error before your next deployment change.

## Platform overview and Spaces

The platform dashboard also has **Platform overview** and **Platform insights** views. In **Platform overview**, choose the period and open a space from a domain table. The Reports link is available where that space has Reports enabled.

Open **Spaces** for **Health**, **Onboarding** and **Announcements**. The Health cards have **Details**, **Open console** and **Manage** controls. See [Space health, service pauses and closure](help:superadmin/space-lifecycle) for suspension, read-only mode, ownership and archive schedules.

**Web telemetry** under platform Analytics controls the central public site. Each space has its own
settings; platform choices are not a fallback for space sites. Providers remain off until configured
and consented. External destinations need operator approval and matching Content Security Policy.

> **Who can do this:** the platform superadmin. Hidden on a single-space installation's own domain.
