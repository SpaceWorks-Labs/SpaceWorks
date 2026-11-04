---
title: Health checks and logs
summary: Check the server is alive and ready, read the logs, and recover the superadmin account.
order: 70
keywords: health, readiness, liveness, logs, monitoring, metrics, compose, troubleshooting, recover superadmin, password reset
---
## Health

1. `GET /api/v1/health/` answers when the app is alive.
2. `GET /api/v1/health/readiness/` answers when it's ready; check it after updates and restores.
3. The superadmin's **Platform dashboard** runs the deeper checks: backups, off-site copies, scheduler, updates, email, storage and domain.

Readiness fails closed when an encryption key is missing or doesn't match, so a "temporarily unavailable" answer often means a key problem.

## Logs

1. List the containers with the compose wrapper script in `scripts/`.
2. Read the backend's logs through the same wrapper.
3. After a failed update, also read the migrate and readiness containers' logs; failed one-off containers are kept for you.
4. Match lines across services by their request ID. Production logs are JSON.

![Screenshot: backend logs through the compose wrapper](screenshot:op-logs)

Always use the wrapper rather than plain `docker compose`, and read the logs before restarting anything.

## Locked out of the superadmin account

From the server, the host operator can set a new password for the superadmin, or reset its two-step sign-in, with the management commands in the self-hosting guide.

> **Who can do this:** the host operator.
