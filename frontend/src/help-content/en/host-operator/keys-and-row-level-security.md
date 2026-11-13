---
title: Encryption keys and row-level security
summary: Rotate or emergency re-key one space's encryption, and check that the database keeps spaces apart.
order: 50
keywords: encryption keys, rotate, re-key, emergency, search key, browser key, row-level security, rls, report-only, enforced, database role
---
## A space's encryption keys

1. In `/control/`, open the space and follow **Rotate or re-key**. The page is **Encryption keys**.
2. Read the active data key and search key versions.
3. **Rotate the key**: new data uses a new key at once and older records are re-encrypted in the background.
4. **Emergency re-key** does the same and tells the space's managers when it starts and finishes.
5. **Rotate the search key** re-indexes the space. **Issue a new browser key** replaces the public site key; the old one keeps working for 72 hours.
6. Confirm your identity, then watch **Recent key jobs**.

![Screenshot: the Encryption keys page](screenshot:op-space-keys)

One job runs per space at a time, every action is audited in the space, and backups stay restorable.

## Row-level security

The database itself can keep spaces apart, as a backstop behind the app's own checks.

1. In `/control/`, open **Row-level security** and read the mode: **Enforced**, **Report-only**, **Inactive** or **Off**.
2. **Report-only** means the app connects as the database owner: switch it to the narrower bundled app role to enforce.
3. **Inactive** means the role bypasses the rules (a superuser, or one allowed to bypass them).
4. If any tables are missing their rules, sync them (migrations do this too) and check again in strict mode.

The app always starts, whatever the mode; report-only logs cross-space reads without stopping them. Never set the probe role on a production server.

> **Who can do this:** the host operator, signed in as the platform superadmin.
