---
title: Move a space to another server
summary: Move a space between two Space Works servers, or hand it over to its own self-hosted server.
order: 90
keywords: tenant migration, move space, transfer, self-host, export, import, cut over, fingerprint, disclosure
---
## Between two servers you run

Open **Tenant migration** on both servers and work through the steps in order:

1. **Review disclosure** (source): approve exactly whose personal details travel.
2. **Pin deployments**: compare fingerprints with the other operator outside the app.
3. **Encrypt export** (source).
4. **Import & resolve** (target): decide each person: link to an existing account, keep as a walk-in, or withhold.
5. **Verify & materialise** (target).
6. **Cut over**: the source stops taking changes and the target goes live.

![Screenshot: the Tenant migration steps](screenshot:sa-tenant-migration)

It's one-way. The source space is archived, not deleted, and only one server is writable at a time. Staff sign-ins travel with the space.

## A space moving to its own server

A Space Manager asks from **Backup & restore**, **Move to your own server**.

1. In `/control/`, **Self-host move requests**, approve the request (or reject it).
2. Open it, paste the new server's public key and press **Run export**.
3. Download the encrypted archive and give it, with its checksum, to the new server's operator.
4. Delete the file from this server, and archive the space once the move is confirmed.

Every step needs you to confirm your identity again. The space is read-only while the export runs.

> **Who can do this:** the platform superadmin on each server.
