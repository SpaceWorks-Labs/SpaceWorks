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

Standard Compose containers and Helm configure the worker directory and Gunicorn hooks automatically.
For a custom Gunicorn deployment set `PROMETHEUS_MULTIPROC_DIR` to a process-writable directory dedicated to **one master**
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

## Web telemetry in Reports / Analytics

Provider-by-provider summary (what each collects and how to enable it): [web-telemetry-providers.md](web-telemetry-providers.md).

Web telemetry settings are separate from the Metabase connection. A Space Manager configures a
space under **Reports → Analytics → Web telemetry**; the platform superadmin configures the
central site separately. Turning off the space's Analytics module disables its telemetry. The
space does not inherit the platform's provider settings. No account or provider is configured
automatically, and collection stays off until the chosen purpose is configured and the visitor
consents to it.

Choose at most one **Page analytics** provider: Plausible, Umami, GA4, Firebase Analytics or
PostHog. `none` disables page analytics; Umami is a suggested choice, not an enabled default.
For Umami supply its website UUID and an operator-approved HTTPS origin. GA4 uses its `G-...`
measurement ID. Firebase Analytics uses the public Firebase project and web-app identifiers.
Enter its `G-...` measurement ID in the Firebase measurement field and leave the general site ID
empty for that provider. Firebase Performance and browser notifications do not require that ID.
Choose GA4 **or** Firebase Analytics for a page, not both: Firebase Analytics can represent the
same GA4 property. Turn off provider automatic page views and enhanced measurement; page views
must use the application's sanitized route templates rather than raw URLs or identifiers.

**Session replay** is independently optional: choose `none`, Clarity or PostHog. If PostHog is
selected for both page analytics and replay, use the same project key and effective origin. Replay
is limited to the anonymous public `/about` page; other routes are excluded and crossings use a
full document navigation. It requires its own consent and careful provider-side privacy setup: mask inputs and text, block
images, video, canvas and frames, disable automatic capture, console and network bodies/headers,
and verify that URLs and DOM attributes cannot expose private data. Masking text alone does not
mask attributes or query strings. Enable replay only after the deployment has verified these controls
on its real pages. Sensitive, authenticated, credential, payment, evidence and unknown routes
must remain excluded. Visitors may withdraw consent; withdrawal cannot erase data already held by
the provider, so follow the provider's retention and deletion procedures.

Sentry web diagnostics and Firebase Performance are separately optional and require diagnostics
consent. The Sentry **public DSN** is a browser ingestion address; do not enter a server auth token
or private key. For Firebase Performance use manual, sanitized traces; do not enable automatic
network traces containing URLs or payloads. A sample rate is a fraction from 0 to 1. Defaults are
1.0 for Sentry and 0.1 for manual Firebase Performance, with both switches off; a rate of 0 is
valid and sends no samples. Firebase web
configuration uses public project identifiers; the server's encrypted Firebase service-account
credential is managed separately and must never be pasted into web telemetry settings.

An operator must approve external destinations on **both** the backend and frontend using the same
comma-separated `WEB_TELEMETRY_ALLOWED_ORIGINS` HTTPS origins, without paths, credentials, queries
or fragments. The frontend's Content Security Policy must also permit the fixed SDK and ingestion
origins; this approval does not itself enable a provider or replace consent. Self-hosted endpoints
must be explicitly approved. Empty Plausible and PostHog endpoints use their adapters' fixed defaults;
Umami needs an explicit origin. Do not configure an arbitrary script URL.

The default same-origin `/api` proxy lets the browser check for a session without rotating it.
When that check cannot establish an anonymous browser, including cross-origin cookie uncertainty,
telemetry stays off. While authentication is loading or unknown, collection stays off; start only
after the browser is positively known to be anonymous. Application page-view events use approved
public route templates. A replay SDK may observe an approved public URL and pseudonymous transport
metadata, so verify its actual payloads and provider retention rather than assuming those disappear.
Query strings, fragments, credentials, customer details, evidence and notification content must not be sent. Test the actual
network payloads and navigation boundaries for each enabled provider before relying on these controls.

### Firebase browser notifications

Browser notifications are a separate opt-in from analytics and use the Notifications module and
web-push feature gates. The platform superadmin configures public Firebase web identifiers and the
VAPID public key in **Platform → Firebase web settings**, independently of Analytics. The server
uses the existing encrypted platform Firebase service-account credential; its project must match
the browser's Firebase project. Browser permission, a supported
browser, the configured VAPID key and a compatible service worker are also required. The browser
must prove it controls its registration before activation. The worker must accept a wake-up only for the
current account's ownership epoch. A push must carry no private message: the worker shows a constant
generic notice, and the fixed inbox link opens the app for authenticated, scoped access. Existing W3C browser alerts and native push
remain separate. Check worker coexistence, account switching, revocation and real delivery for the
deployment before offering Firebase browser alerts. Configuration alone does not establish delivery.

## Reports and analytics by module

Every module reports. The **Reports** page is one hub grouped the same way as the module switches
(Inventory, Stocktake, Machines, Events, Bookings, Membership, Notifications, Reports, Payments,
Mobile apps, Connected devices, Shop), with a search box, one chip per module group, and a pin
(star) beside each report. Pins are kept in your browser, like the theme. A report appears only
while its module is on and only to a role holding the action it needs; when nothing is listed the
page says whether the module is off or your role unlocks no report. Each module's own page ends
with an **At a glance** card whose **All reports for this module** link opens the hub on that group
(`?group=<module group>`). Superadmin **Platform Insights** has a **Reports by module** card in the
same grouping that opens the hub in its all-makerspaces mode (`?scope=all`).

Every report supports the same delivery services: on-screen table and chart, CSV and XLSX export
(each export is audited), scheduled email, and the API
(`/admin/makerspace/{id}/analytics/{key}` and `/reports/{key}/export`; superadmin roll-ups use
`/admin/analytics/{key}`). Roll-ups are aggregates per space and never carry a person's details.
Metabase views are listed in [analytics-views.md](analytics-views.md); Grafana has one starter
dashboard per area.

| Module group | Reports (per space) | Metabase views | Grafana |
| --- | --- | --- | --- |
| Inventory (loans, QR, evidence, import, containers) | loan throughput, most lent, asset usage, overdue, damaged and lost, inventory control, QR scans, evidence compliance, import quality, valuation | inventory views, loan contexts | Inventory and loans |
| Stocktake, transfers, procurement | stocktake variance, stock transfers, stock health, procurement performance | inventory views, procurement | Inventory and loans |
| Machines (service, printing, maintenance) | machine usage, downtime, service and queue times, printer jobs, consumables, **machine access grants**, repairs | machine views, **machine_access_grants** | Machines |
| Events | attendance, signups, revenue, funnel, feedback, **event certificates issued** | event views, **event_certificates** | Events |
| Bookings | utilisation, occupancy, lead time | booking views | Bookings |
| Membership (members, presence, cards) | growth, retention, revenue, join funnel, registers, **card studio activity**, member card issuance | membership views, **card_jobs** | Membership |
| Notifications and channels | communications health | none | none |
| Reports | **report schedules and saved views** | none | none |
| Payments and finance | cash book, revenue over time, ageing, reconciliation, donations, GST | payments, donations | Money |
| Mobile apps | mobile devices, mobile sign-in | none | none |
| Connected devices | device health, **device adapter activity** (usage, access decisions, commands, telemetry, media, typed events) | **adapter_usage**, **adapter_access_decisions** | Machines |
| Shop | shop sales, product sales, stock value | shop views | none |
| Platform (superadmin) | platform services, platform usage, **profile and username adoption**, module health | none | none |

Bold items are new in 0.12.0. Space display and the public stats page store settings only and record
no activity, so they appear in the module health report. The full per-module matrix is regenerated by
`handover/reports/report_coverage_matrix.py`.

## Existing Plausible-compatible page views

Analytics is disabled by default. Configure all three variables, consistently on backend and frontend:

```dotenv
WEB_ANALYTICS_SCRIPT_URL=https://analytics.example/js/script.manual.js
WEB_ANALYTICS_COLLECT_URL=https://analytics.example/api/event
WEB_ANALYTICS_DOMAIN=makerspace.example
```

For this existing deployment-level integration use a Plausible-compatible **manual** script variant. Script URL paths must contain
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
committed deployment environment. The all-in-one image is retired; existing single-box installations
must follow the [standard-container switch steps](update-recovery.md#moving-off-a-single-box-install).
