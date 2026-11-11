---
title: Set up offsite backups and restore
group: How-to guides
order: 110
summary: Add an S3-compatible offsite destination, check that copies are verified, and pick the right restore.
---

# Set up offsite backups and restore

SpaceWorks makes encrypted archives on a schedule. An **offsite copy** puts a verified duplicate in a bucket you own, so losing the server does not lose its backups.

## What exists

| Layer | When | Restore with |
| --- | --- | --- |
| Whole-deployment archive | Nightly at 02:00, or on demand | `scripts/import-backup.sh` then `scripts/restore.sh` (disaster restore) |
| One-space archive | Nightly, or **Back up now** | In the app: preview, confirm with your password and the space slug |
| Pre-update dump | Before every update | The documented offline procedure |
| Offsite copy | Every five minutes while a destination is enabled | Fetch it back, then restore as above |

Nightly archives keep 7 daily and 4 weekly copies. The newest verified offsite copy of each destination is never pruned.

## Add an offsite destination (superadmin)

1. Create a private bucket at any S3-compatible provider (R2, B2, S3, Supabase Storage, MinIO elsewhere) and an access key that can read, write and delete in it.
2. Open **Platform > Data & recovery > Offsite copies** and expand **New destination**.
3. Enter a **Name** (lowercase letters, digits and hyphens, such as `r2-offsite`), the **Bucket**, the **Endpoint URL** (blank for AWS), optional region, folder prefix and addressing style, **Keep copies for (days)** (1 to 3650), the **Access key ID** and **Secret access key**.
4. Tick **Push new backups here** and save.
5. Press **Test**: it writes, reads back and deletes a probe object. Then press **Push now** to send the newest backup immediately.
6. Open **Copies** to confirm each upload shows as verified.

SpaceWorks reads each upload back and checks its size and SHA-256 before it counts as a copy, and re-checks verified copies every 30 days. A failed check stays visible and is retried; it is never silently counted.

> **Note** Pushing now, rotating credentials, retiring a destination and bringing a copy back are destructive or credential-bearing. If you have not signed in within ten minutes they ask for your password again (`recent_reauth_required`). Retiring wipes stored keys but leaves copies already in the bucket.

## Keep your keys safe

The archive carries ciphertext. The platform backup key (`BACKUP_AGE_RECIPIENT`'s identity) must **stay off the server**, and you should keep an independent copy of `.env` somewhere else. Without the keys in `.env`, encrypted fields in a restored backup are unreadable. See [Rotate encryption and secret keys](rotate-keys.md).

## Pick a restore

| Situation | Do this |
| --- | --- |
| One space was damaged | **Backup & restore**, choose the space, preview, restore. A safety backup is taken first |
| The server or database is lost | Disaster restore: install the same release or newer with the same `.env` keys, then `import-backup.sh` and `restore.sh` |
| An update went wrong | Failed updates roll the images back by themselves; going back on purpose means restoring the pre-update dump |
| Moving a space | [Move a space](move-a-space.md) |

A disaster restore enters **quarantine**: a superadmin reviews the result before normal writes resume.

To pull a verified copy back from a destination onto a rebuilt host:

```bash
python manage.py fetch_offsite_archive --destination r2-offsite --archive-id <uuid> --output ./archive.tar.age
```

## Prove it works

- The server drills one space weekly (restores into a throwaway database, checks every row, then destroys it). Failures email the superadmins; see **Platform > Data & recovery > Restore drills**.
- After any restore, `GET /api/v1/health/readiness/` must report ready.

## See also

- [Backup and restore](../backup-and-restore.md) for every command and the outside-database variant.
- [Database recovery after an update](../update-recovery.md)
