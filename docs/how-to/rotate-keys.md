---
title: Rotate encryption and secret keys
group: How-to guides
order: 190
summary: Which keys can be rotated, how, and which ones you must never change casually.
---

# Rotate encryption and secret keys

Different keys have different rotation stories. Rotating the wrong one casually can make data unreadable, so read the row for the key you mean.

## Quick guide

| Key | Rotate? | How |
| --- | --- | --- |
| A space's data key (per-space DEK) | Yes, routine or after an incident | Platform console, background re-encrypt |
| A space's public site key (`public_api_key`) | Yes | Old key keeps working for a grace window (72 hours by default) |
| API client secret | Yes | New secret now, old secret works for 24 hours |
| Platform or server backup key | Yes | `backup_keys` |
| Audit signing key | Yes | `rotate_audit_signing_key` |
| `PII_MASTER_KEY` (key-encryption key) | Yes, with the previous value kept | Two-step rewrap |
| `SECRET_KEY` | Avoid | Invalidates sessions and signed tokens |
| `API_CLIENT_ENC_KEY` | Do not rotate casually | Encrypts integration secrets; changing it strands saved tokens and passwords |
| `PII_SEARCH_HASH_KEY` | Only with a full reindex | Fenced maintenance, no mixed-key traffic |

> **Warning** Losing or changing `SECRET_KEY`, `API_CLIENT_ENC_KEY`, `AUDIT_MAC_MASTER_KEY`, `PII_MASTER_KEY`, `PII_SEARCH_HASH_KEY`, `ACCOUNT_PII_MASTER_KEY`, `EVENT_REGISTRATION_CREDENTIAL_*` or `PUSH_TOKEN_HMAC_KEY` makes the data they protect unreadable. Keep `.env` backed up off the server, in separate custody from your database backups. Updates never regenerate an existing key.

## A space's data key (superadmin)

1. Sign in to the platform admin at `/control/`, open **Makerspaces**, pick the space and open its **Keys** page.
2. Choose **Rotate the key** (a new key version becomes the write key at once and a background job re-encrypts the space's data to it) or **Emergency re-key** (the same, plus a notice to the space's managers).
3. You may be asked to confirm your identity again (a recent sign-in is required).

Old versions are disabled one by one once nothing references them. Immutable history is never rewritten; that version stays unwrappable and is listed on the job. Archives stay readable. Progress and failures show on the job, and a space's managers can see the history under **Security > Encryption key history**. The control plane at `/control/` offers the same action as a fallback.

## API client and public site keys

- **API client secret.** In **API access**, open the client's menu and choose **Rotate secret**. The old secret works for 24 hours; rotating twice inside the window invalidates the oldest immediately.
- **Public site key.** Rotating issues a new key at once; the previous one is accepted for `PUBLISHABLE_KEY_ROTATION_GRACE_HOURS` (72) and then refused.

## Backup keys

Generate a new age key pair on a trusted machine, put the **public** key in `BACKUP_AGE_RECIPIENT`, restart, then record the rotation:

```bash
python manage.py backup_keys rotate --kind platform --actor-id <superadmin id>
python manage.py backup_keys status
python manage.py backup_keys reencrypt --actor-id <superadmin id>
```

Recording retires the older key: backups refuse a retired key from then on. Whole-deployment archives are sealed to the platform key alone, which never lives on the server, so keep them until they expire or purge them (`backup_keys purge --archive <id>`).

## The key-encryption key (`PII_MASTER_KEY`)

Set the new value as `PII_MASTER_KEY` and the old one as `PII_MASTER_KEY_PREVIOUS`, restart, rewrap every data key, verify each unwrap, then remove the previous value and restart. Application data is not rewritten. Full steps, including AWS KMS and the search key, are in the [scoped PII runbook](../scoped-pii-encryption.md#key-rotation-backup-and-incident-recovery).

## Audit signing key

```bash
python manage.py rotate_audit_signing_key --global --actor-user-id <id> --dry-run
python manage.py rotate_audit_signing_key --global --actor-user-id <id> --execute
```

Use `--makerspace-id <id>` instead of `--global` for one space. No key material is passed in.

## See also

- [Back up and restore](offsite-backups.md)
- [Environment reference](../environment-reference.md)
