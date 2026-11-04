---
title: The /control/ admin
summary: The platform's back-office pages, what they're for, and how to reach them safely.
order: 110
keywords: control, django admin, back office, archive space, purge, backup keys, drills, login methods, scheduled tasks, ip rules
---
`/control/` is the platform's back office. Most day-to-day work happens in the console; `/control/` holds the rarer, heavier tools.

## What it's for

- The list of spaces: archive, unarchive, purge and archive requests.
- Purging a feature's data with a preview.
- Backup keys, restore drills and notices.
- Self-host move requests and hosting requests.
- Login methods and social sign-in.
- Platform email, SMS and push.
- Scheduled task runs, storage, and IP allow and deny rules.
- Encryption keys per space, and row-level security status.

![Screenshot: the /control/ home](screenshot:sa-control)

## Reaching it

1. Ask the host operator to open access, through the proxy or an SSH tunnel.
2. Open `/control/` and sign in with the superadmin account.
3. Complete two-step sign-in at its own step.

It's off the public address by default. The host operator turns on access through the proxy or an SSH tunnel; see [Reach /control/ safely](help:host-operator/control-plane-access). Turn on two-step sign-in before exposing it. Destructive actions ask you to confirm your identity again.

> **Who can do this:** the platform superadmin only.
