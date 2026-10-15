# Monitoring and private web analytics

`/control/storage/` is a read-only control-plane page, linked in Operations. It uses the existing
managed object accounting and PostgreSQL database/table size functions. It does not scan buckets,
change quotas or repair accounting. Hidden makerspace names/counters are excluded; database totals
include the whole deployment. Self-hosted object counters may be zero. The existing superadmin,
active-account, forced-password-change and control MFA boundaries apply. Responses are private/no-store.

## HTTP metrics

Set `ROUTE_METRICS_ENABLED=true` to add counters and latency histograms to the existing
`/api/v1/metrics/` endpoint. It remains hidden with no `METRICS_TOKEN`; pass that deployment secret
as `Authorization: Bearer ...`. Never expose the secret in query strings. Counters distinguish route,
method and status; latency buckets distinguish route and method. Labels use Django's compiled route
templates, never raw URLs, query strings, user IDs or bearer values. Unknown routes/methods use fixed
labels. The recovery gate remains first and can refuse traffic before instrumentation.

Compose and Helm configure the worker directory and Gunicorn hooks automatically. The all-in-one
supervisor clears a shared directory once before launching its two masters. For a custom Gunicorn deployment set `PROMETHEUS_MULTIPROC_DIR` to a process-writable directory dedicated to **one master**
and `GUNICORN_CMD_ARGS=--config python:config.gunicorn_metrics`. Do not use `--preload`. The hook clears
old worker files once before the WSGI app loads and marks dead workers on recycling. Counters and
histograms aggregate across workers, including already-exited workers. Separate masters/pods need
separate directories. The Helm chart supplies an emptyDir and the hooks. Scrape each backend/live
pod endpoint individually rather than load-balancing a scrape across replicas; aggregate by deployment
in Prometheus. Persist and retain metrics in the operator's Prometheus; Django stores no request history.
Latency measures response construction, not the lifetime of streaming/SSE responses.

The development overlay removes `PROMETHEUS_MULTIPROC_DIR` for both runserver services.
They collect in memory in the single serving process, so no worker directory is needed;
counters reset on autoreload or restart. Production keeps the Gunicorn directory lifecycle.

## Optional page views

Analytics is disabled by default. Configure all three variables, consistently on backend and frontend:

```dotenv
WEB_ANALYTICS_SCRIPT_URL=https://analytics.example/js/script.manual.js
WEB_ANALYTICS_COLLECT_URL=https://analytics.example/api/event
WEB_ANALYTICS_DOMAIN=makerspace.example
```

Only a Plausible-compatible **manual** script variant is supported. Script URL paths must contain
`manual` as a separate filename component. Endpoints must use HTTPS without embedded credentials,
query or fragment. The frontend loads the script with manual mode, automatic views disabled and
no-referrer, and submits its own protocol message with a route-template `u` and empty `r`. It sends
no title, account data, cookies, query string, hash, event token or resource identity. Collection failures
are ignored. The script is an operator-trusted integration: select a genuine manual build.

The shared allow-list in `frontend/src/lib/webAnalytics.ts` covers public inventory, events, booking
resources, machines, organizations and general pages. New public booking website routes extend this
table. Private/unknown/query-bearing routes do not inject a script or send views. Before crossing a
bearer boundary the guard removes the script and provider queue, cancels pending collection, and uses
a full document navigation. History transitions through bearer pages reload too. Tickets, claims,
resets, invites, station/kiosk, embeds and re-auth callbacks are excluded.

The frontend nginx startup script validates configuration and writes runtime `config.js` plus CSP
headers; Django extends script-src/connect-src only for configured origins. Caddy preserves those
upstream policies and sets strict-origin referrer policy. HTML has a matching meta policy for static/dev
serving. When analytics is enabled, frontend CSP restricts script/connect origins; declare additional
external API and browser-facing object-storage HTTPS origins in
`WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS` (space-separated origins). Same-origin deployments need none.
Do not put paths or credentials there. Rebuild the frontend image to include the startup script.

Frontend tests cover route-template projection and script/queue removal; the Playwright secrecy test
intercepts only the external analytics service and asserts that bearer values never reach it, including
after navigation. Run it against the real stack with `analytics-secrecy.spec.ts`.

Compose base, bundled production and Cloud forward the optional settings to all backend writers and
the frontend. The existing installer questions/path are unchanged; operators opt in through the
committed deployment environment. All-in-one uses the same runtime config/CSP writer.
