# Decisions: Analytics and reports

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-375 — Org-wide analytics SDK rule
- **Area:** analytics
- **Date:** 13 November
- **Decision:** Android and iOS must support the same optional analytics providers as the web where an official mobile SDK exists, off by default, per deployment, with no personal data and a client tag.
- **Why:** Reason not recorded.
- **Status:** current

### D-357 — Web and app usage analytics by channel
- **Area:** analytics
- **Date:** 12 November
- **Decision:** Counts-only daily activity is tracked per channel (web, ios, android, api_client) with feature-by-channel aggregates (cache counters flushed by Celery beat, audit log untouched). Superadmin gets a "Web and app use" report and Space Managers a variant for their own space; web telemetry events carry a `client` tag. Later additions: new versus returning, distinct accounts, app version and OS distribution, and CSV export.
- **Why:** Operators wanted to tell phone use apart from web use.
- **Status:** current
- **Implemented in:** `backend/apps/analytics/`

### D-327 — Reports coverage per module
- **Area:** analytics
- **Date:** 11 November
- **Decision:** Every module has per-space reports and a superadmin roll-up where meaningful, built on the existing report registry, with all delivery services (on-screen, CSV/XLSX/PDF, scheduled email, Metabase, Grafana, API). One Reports hub groups reports by module, filters by role and hides reports of switched-off modules; a registry-versus-module guard test enforces coverage.
- **Why:** Reports should be discoverable and consistent across modules.
- **Status:** current

### D-326 — Analytics providers and public page allow-list
- **Area:** analytics
- **Date:** 11 November
- **Decision:** Supported analytics tools are Plausible, Umami, GA4, Firebase Analytics and Performance, PostHog, Clarity, Sentry, Grafana, Metabase and Prometheus. The 0.12.0 public pages are added to the analytics route allow-list; display/TV and kiosk routes stay excluded.
- **Why:** New public pages failed closed because they were not on the allow-list.
- **Status:** current
- **Implemented in:** `backend/apps/analytics/`

### D-267 — Grafana design
- **Area:** analytics
- **Date:** 11 November
- **Decision:** Grafana settings extend the existing AnalyticsConnection / PlatformAnalyticsConnection rows (`provider` metabase|grafana|both, default metabase; Fernet-encrypted token, org id, listed dashboards). Embedding uses Grafana public dashboards plus server-side PNG render; isolation is enforced by the space's RLS login. A space's Grafana must be on a public address unless the operator sets `GRAFANA_ALLOW_PRIVATE_HOSTS`; the provisioning bundle never contains the password; static hosting gains `FRAME_ORIGINS`. Built-in machine types no longer appear in a space's views when analytics or machines are off.
- **Why:** Grafana OSS has no per-dashboard signed embed; reusing existing rows avoids a new model.
- **Status:** current
- **Implemented in:** `backend/apps/analytics/grafana_bundle.py`, `backend/apps/analytics/grafana_client.py`

### D-263 — Grafana support in the analytics module
- **Area:** analytics
- **Date:** 11 November
- **Decision:** The `analytics` module supports Grafana alongside Metabase, per space and platform-wide, reusing the per-space read-only Postgres login with row-level security and curated views. It offers connection settings (encrypted token), a downloadable provisioning bundle and staff-console dashboard embedding. It is gated by `view_analytics`, audits credential create/rotate/revoke/view, keeps the platform connection superadmin-only and is inert when the module is off. Every analytics tool works at both scopes with strict isolation: a space's tools only ever see that space's data, platform views are superadmin-only, per-space telemetry sends only that space's page events, and tests pin each property.
- **Why:** Operators asked for Grafana parity with Metabase at both scopes.
- **Status:** current
- **Implemented in:** `backend/apps/analytics`, `docs/grafana-setup.md`, `docs/analytics-views.md`

### D-213 — Web telemetry belongs in Reports/Analytics configuration
- **Area:** analytics
- **Date:** 8 Nov 2026
- **Decision:** Sentry, PostHog, Firebase web (Analytics/Performance/FCM), GA4/Umami and Clarity are options under Reports/Analytics settings, all off until configured and consented per purpose, using scoped settings and safe public projections. No mobile SDK work is included, and browser push stays governed by notification/push permissions, not the analytics switch.
- **Why:** Reason not recorded
- **Status:** current

### D-205 — Public stats are configurable per area
- **Area:** analytics
- **Date:** 7 Nov 2026
- **Decision:** Everything on public stats is configurable by the matching area manager (Inventory, Events, Machines, Bookings); the Space Manager keeps page-wide controls. Per-widget visibility defaults to the current display, unknown or unauthorized keys are rejected atomically, and module-off hiding, projection privacy, small-number suppression and the borrower-name opt-in are preserved on the page and the TV board.
- **Why:** Reason not recorded
- **Status:** current

### D-183 — Superadmin platform overview and module separation audit
- **Area:** analytics
- **Date:** 5 November
- **Decision:** The superadmin gets a platform overview with combined totals across servable spaces and a per-space breakdown (people, lending, machines, events, bookings, membership, money, modules, operations), with period presets, drill-down and CSV export. Money is grouped per currency and never summed across currencies; no member names appear; archived or hidden spaces are excluded by default. Every module and capability switch must behave when off: no route answers except 404, no navigation, notification or scheduled task, data kept, purge removes only that module's rows, and a build with tombstoned apps still boots.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/config/control_dashboard.py`, `docs/MODULES-OFF.md`
