---
title: Monitoring
group: Hosting
order: 120
summary: Health endpoints, the Platform dashboard and problem checks, Prometheus metrics and the Grafana and Metabase analytics options.
---

# Monitoring

## Health endpoints

Two unauthenticated endpoints on the backend:

| Endpoint | Meaning |
| --- | --- |
| `GET /api/v1/health/` | The process is up. Returns `{"status": "ok"}`. It answers 503 while the recovery gate is closed (database unreachable, or a restore is running). |
| `GET /api/v1/health/readiness/` | The app is ready to serve: use it after an update or restore. |

The Compose files already use these for container health checks and for the updater's readiness wait.

## Platform dashboard and problem checks

Active superadmins have a **Platform dashboard** in the staff console with platform counts, per-space usage,
delivery counts and backup, offsite-copy, scheduler and update state. It runs an explicit list of problem
checks on demand, each returning `ok`, `warn` or `error` with a plain message and a link to fix it. Examples:
a backup older than one and a half times the backup interval warns and older than three times errors (36 and 72 hours with a daily schedule); a failed or abandoned offsite copy
errors; a scheduler that has not run recently warns. Space Managers have a **Usage and limits** tab for their
own space. See [Own and hosted spaces](managed-spaces.md#who-sees-usage).

## Metrics

`GET /api/v1/metrics/` serves Prometheus metrics. It is hidden (404) until you set `METRICS_TOKEN`; pass it as
`Authorization: Bearer <token>`, never in a query string. Keep `/api/v1/metrics*` unreachable from the public
internet.

Set `ROUTE_METRICS_ENABLED=true` to add request counters and latency histograms by route template, method
and status. Labels never contain raw URLs, query strings, user IDs or tokens. The standard Compose files and the
Helm chart configure the multi-process directory automatically. Persist and retain the metrics in your own
Prometheus; Space Works stores no request history. Scrape each backend and live process individually rather
than through a load balancer. The details are in [Monitoring and private web analytics](../monitoring-and-analytics.md).

Optional error tracking: set `SENTRY_DSN`. The SDK loads only when set, and personal data is never sent.

## Logs

Logs are one JSON object per line outside development, each carrying the request's `X-Request-ID`. On an
installed server:

```bash
scripts/spaceworks-compose.sh bundled logs backend
```

The installer's own log is `install.log` in the install directory. Business events are in the audit log; see
[Logging and audit](../logging-and-audit.md).

## Analytics with Grafana or Metabase

Space Works does not bundle Grafana or Metabase. With the `analytics` module on (it is off by default), each
space gets a **read-only database login** limited to curated views, and the platform gets its own login. Point
either tool at them, or both:

- [Grafana setup](../grafana-setup.md), including a ready-made data source and starter dashboards.
- [Metabase setup](../metabase-setup.md), including embedding dashboards in the staff console.
- [Analytics views](../analytics-views.md), the list of views and what they expose.

## Scheduled jobs

The bundled Celery beat runs scheduled jobs, including return reminders and backups. The Platform dashboard's
scheduler check warns if it stops. See [Backups and restore](backups.md#verify-a-backup) for the drills.

## Outbound messages: worker health and queue backlog

Email, SMS, push, chat and webhook notifications are sent by the Celery worker. If the worker stops, requests keep working but nothing is delivered and the backlog grows (it is kept, and sends when the worker returns; sealed one-time codes expire after 15 minutes).

- **Worker health.** The Platform dashboard shows the last worker heartbeat (each mail task records one). A stale heartbeat with a growing backlog means the worker is down: `docker compose ps worker` and `docker compose logs worker`.
- **Backlog.** In `/control/`, open Email logs (status `pending`/`failed`) and Notification envelopes (`processed at` empty). Redis queue depth: `docker compose exec redis redis-cli llen celery`.
- **Stuck jobs.** Fan-out jobs that failed six times are marked dead and log `fanout_job_dead`; one-time-code mail logs `transient_email_failed` and `transient_payload_expired`. Alert on those log lines.
- **Brokerless and free installs** have no separate worker; messages are sent inline by the web container and the scheduler tick drains retries.

