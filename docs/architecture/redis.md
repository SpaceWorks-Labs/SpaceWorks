---
title: Redis
group: Architecture
order: 85
summary: What uses Redis, what happens while it is down or absent, the settings, sizing and security.
---
# Redis

SpaceWorks uses Redis for three separate jobs. Each can point at its own Redis, and all three are optional:
an install can run with **no Redis at all** (the installer's "None (cron mode)" choice).

| Job | Setting | Without it |
|---|---|---|
| Celery broker (the job queue) | `CELERY_BROKER_URL` | Jobs run inline in the request that starts them; scheduled jobs run from `run_scheduled_tasks` (cron mode). |
| Django cache (rate limits, short-lived state, read-through caches) | `CACHE_URL`, default: the broker URL | The shared database cache (`spaceworks_cache` table). Never a per-process cache. |
| Live updates (Server-Sent Events over pub/sub) | `LIVE_REDIS_URL`, default: the broker URL | `/api/v1/live/` answers 503 and the browser polls. |

Celery results are not stored (`CELERY_RESULT_BACKEND` empty). Sessions and the django-axes lockout records
live in PostgreSQL, not Redis.

## What happens while Redis is down

Redis going away must never take sign-in down with it, and must never make a security limit unlimited.
`config/redis_cache.py` (`ResilientRedisCache`) wraps Django's Redis cache: when a call fails with a
Redis error, that call is answered from a small per-process memory cache instead, and the process skips
Redis for the next 5 seconds (so a dead Redis costs one connect timeout per process per 5 seconds, not one
per call). One warning, `redis_cache_unavailable`, is logged per outage per process.

| Kind of use | During an outage | Why that is the right rule |
|---|---|---|
| Rate limits and lockout counters (every DRF throttle, sign-in failure counters, IP auto-block, PIN budgets, OTP budgets) | Keep counting, per process: a limit is at most *rate x workers* | Sign-in keeps working (auth paths fail open), but a limit is never unlimited. Password lockouts (django-axes) and MFA attempt counts are in the database and unaffected. |
| Read-through caches (login-method switches, IP rules, limit defaults, public pages, share cards, stats) | Miss and read the database, as on a cold cache | The database is the source of truth. |
| Single-use claims: signed-request nonces, one-time download links, push-registration proofs | **Refused** (`claim_once` raises `SharedCacheUnavailable`) | A claim held in one process only would let a replay through on another worker. Signed requests get `503 replay_guard_unavailable` with `Retry-After: 5`; the move download link answers `503 shared_cache_unavailable`; the push proof answers 429. |
| Dedupe keys (GitHub verify queue, adapter notices, audit-once windows) | Deduplicate per process | A duplicate notice or audit row is the safe direction. |
| Short-lived state (kiosk sessions, display pairing, camera frames) | Other workers do not see it, so a session reads as expired | Fails closed: the person starts again. |
| Celery broker | `.delay()` raises after a short connect timeout; callers catch and log it. Email, notifications, card jobs, webhooks, backups and exports are database rows that a sweep re-drives | The row stays pending and is picked up after the outage. |
| Live updates | The stream answers 503; browsers poll | Live events are hints; screens refetch through the normal API. |

Writes made during an outage stay in the process that made them. A cache delete that Redis never saw is
bounded by that key's own expiry, which is why every key has one (below).

## Every Redis touchpoint

| Touchpoint | Code | Keys | Expiry |
|---|---|---|---|
| Broker | `config/settings_delivery.py`, `config/settings.py`, `config/settings_redis.py` | Celery's own queues | none (never evicted: see sizing) |
| Baseline throttles | `config/throttles.py` | `throttle_deployment_*_{device,user,client,ip}:<window>` | one window |
| Scoped throttles | `apps/*/throttles*.py`, views | `throttle_<scope>_<ident>`; emails, phones and usernames are HMAC fingerprints | the rate window |
| Sign-in failure, risk and IP guard counters | `accounts/ip_guard*.py`, `login_risk_signals.py` | `sec:*` with HMAC-salted IP and account keys | the guard window |
| Login-method and member-account switches | `accounts/login_methods.py`, `member_identity.py` | one last-known-good key each | none on purpose: one key, read only when the database read fails |
| Limit defaults, throttle-rate overrides | `managed_hosting/limit_defaults.py`, `throttle_rates.py` | two keys plus one last-known-good | 60 s / 300 s; last-known-good none on purpose |
| IP rules, verified hosting domains, social CSP origins | `accounts/ip_rules.py`, `makerspaces/hosting.py`, `accounts/social_csp.py` | one key each | 60 s / 300 s / 60 s |
| Provider keys (JWKS, OIDC discovery) | `accounts/social_jwt.py`, `oidc_browser_http.py` | per provider | configured seconds |
| Signed-request nonces | `inventory/middleware_nonce.py` | `apiclient-hmac-nonce:<sha256>` | 2 x clock skew + 1 s |
| API client last-seen telemetry | `apiclients/telemetry.py` (direct client) | `apiclients:usage:<kind>:<minute>` hashes | 2 days; flushed every minute |
| Personal access token rate | `apiclients/person_auth.py` | `person-credential:<key>:<minute>` | 120 s |
| Adapter PIN, detection, kiosk, frames, notices | `devices/services_adapter_*.py`, `adapter_notifications.py` | binding, watch or session ids | 60 s to 15 min |
| Display pairing budgets | `presence/display_pairing.py` | hashed network, space id | 30 min / 1 h |
| Public pages, share cards, stats, TV | `makerspaces/website_serving.py`, `events/share_cards.py`, `inventory/public_stats_cache.py`, `presence/cache.py` | content digest or space id | 30 s to 1 h |
| Public profile generations and GitHub calendar | `makerspaces/public_profile_cache.py`, `profile_github*.py` | profile or account id | 8 days (generations), 25 h, 7 days |
| Telegram bot name | `integrations/notification_telegram.py` | config id, generation, HMAC of the token | 1 day |
| Platform overview, problem checks, scheduler diagnostics, worker heartbeat | `operations/*`, `integrations/health_status.py` | fixed keys | 60 s to 1 h; heartbeat none (one key) |
| Archive key progress, move download links, push proofs | `backup/space_archive_keys.py`, `tenant_migration/views_selfhost_moves_platform.py`, `notifications/browser_firebase_*.py` | archive id, token hash, HMAC | 5 min to 24 h |
| Live updates | `operations/live.py` (direct client) | pub/sub channels `spaceworks:live:{makerspace,user}:<id>` | not stored |
| Metrics queue depth | `operations/views_metrics.py` (direct client) | reads the queue length | - |

Rules the inventory follows, held by `tests/test_redis_cron_mode_0120.py`:

- **Every key expires**, except the four single keys listed as "none on purpose".
- **No secret or address in a key.** Tokens, emails, phone numbers, usernames and IPs used for security
  counters are HMAC fingerprints. Values hold ids and timestamps; the kiosk session holds the member id.
- **Tenant keys carry the space or a globally unique row id**, so two spaces never share a key unless the
  content is identical (content-addressed share pages).
- **One deployment per Redis database.** Keys and live channels are not prefixed per deployment, so two
  deployments must not share a Redis database number. Use a different number (`/1`) or instance.

## No Redis: cron mode

`SPACEWORKS_REDIS=none` (installer choice 3) applies `docker/compose.no-redis.yml`: Redis and the Celery
worker are not started, and the `beat` container runs `run_scheduled_tasks --due-only` once a minute for both
schedules. In that mode:

- the cache is the database cache, shared by every web worker, so rate limits stay deployment-wide;
- every beat task is also in the cron catalogue (`legacy_schedule()`), so nothing scheduled is skipped;
- jobs run inline in the request that starts them, except the persisted ones (exports, imports, bulk
  imports, audit verification), which the worker picks up, and the GitHub ownership check, which
  waits for the daily refresh instead of calling GitHub inside a request;
- API client last-seen times are kept in the database cache and flushed every minute;
- nothing imports or connects to Redis at startup;
- live screens poll.

A manual "Back up now" or restore drill also runs inline, inside the request's timeout
(`GUNICORN_TIMEOUT`, 60 s). A large space should use the nightly backup, which runs from the scheduler.

## Settings

| Setting | Notes |
|---|---|
| `CELERY_BROKER_URL`, `CACHE_URL`, `LIVE_REDIS_URL` | `redis://` or `rediss://`. Blank broker means inline jobs. |
| `REDIS_IMAGE_TAG` | Bundled image, pinned (`7.4.11-alpine`). |
| `REDIS_MAXMEMORY` | Bundled memory cap, default `512mb`. |

Fixed in code, not settings: the cache uses a 1 s connect and 2 s read timeout; the broker a 5 s connect
and 30 s socket timeout and a **6-hour visibility timeout** (with `acks_late`, a message not acknowledged
within that window is handed to a second worker while the first still runs it; Celery's one-hour default is
shorter than a large backup).

## Sizing and persistence

The bundled Redis runs with `--appendonly yes --appendfsync everysec` on the `redis_data` volume, so queued
jobs survive a restart, and with `--maxmemory-policy volatile-lru`: only keys with an expiry are evicted, and
every cache key has one while the Celery queues have none. **The broker is never evicted.** If memory fills
with queued jobs, Redis refuses new writes instead; the cache then degrades as described above.

Most installs use well under 50 MB. Camera frames (60 s each) and share-card images (1 h) are the largest
values; raise `REDIS_MAXMEMORY` for many live camera watches.

For an outside Redis: use `noeviction` or `volatile-lru` on the instance that holds the broker, never
`allkeys-*`. To give the cache its own eviction policy, point `CACHE_URL` at a second instance with
`allkeys-lru`. Turn on AOF or RDB persistence for the broker.

## Security

- The bundled Redis listens only on the private Compose network and is never published on a host port.
- An outside Redis should require a password or ACL user and TLS. Put both in the URL:
  `rediss://USER:PASSWORD@host:6380/0`. A `rediss://` broker or result URL with no `ssl_cert_reqs`
  verifies the server certificate (`config/settings_redis.py`); the cache and live clients verify by
  default too. Add `?ssl_cert_reqs=none` only for a self-signed test server.
- The URLs are secrets: backups and tenant moves treat them as secret-bearing settings, and they never
  appear in logs.
- To password-protect the bundled Redis too, override its `command` with `--requirepass` and use
  `redis://:PASSWORD@redis:6379/0` for the three URLs.
