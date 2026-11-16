---
title: Environment keys and rotating them
summary: The secrets in .env that matter most, and how to rotate the encryption keys safely.
order: 40
keywords: env, environment, keys, secret, rotate, rotation, pii key, encryption, backup key, secret_key
---
The installer generates every key in `.env` (readable only by its owner) and updates never replace them. Losing a key makes the data it protects unreadable, so back `.env` up off the server.

## The keys that matter most

- `SECRET_KEY`: signs sessions. Changing it signs everyone out.
- The personal-data keys (`PII_MASTER_KEY`, `PII_SEARCH_HASH_KEY`, `ACCOUNT_PII_MASTER_KEY`): encrypt names, emails and phone numbers.
- `AUDIT_MAC_MASTER_KEY`: lets the audit log prove it hasn't been altered.
- `API_CLIENT_ENC_KEY` and the event credential keys: encrypt stored integration secrets. Don't rotate these casually.
- The database passwords.

## Rotate the personal-data master key

1. Set the new key, and move the old one to `PII_MASTER_KEY_PREVIOUS`.
2. Restart.
3. Re-wrap every space's keys, and check it finished.
4. Remove the previous key and restart again.

![Screenshot: the environment reference for the personal-data keys](screenshot:op-env-keys)

Rotating the search key also needs a maintenance pause, because every search index is rebuilt.

## Rotate the backup key

Set the new recipient, then use the backup key tools to rotate, check the status and re-encrypt existing archives.

## One space's keys

For a single space, use its **Encryption keys** page instead; see [Encryption keys and row-level security](help:host-operator/keys-and-row-level-security).

> **Who can do this:** the host operator, on the server.
