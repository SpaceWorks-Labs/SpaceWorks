# Web telemetry providers

Every provider below is **off** until two things are true: a Space Manager (or, for the central
site, the platform superadmin) has configured it under **Reports -> Analytics -> Web telemetry**, and
the visitor has agreed to that provider's purpose in the Privacy preferences box. Until then no script
is loaded, no request is sent and no cookie or storage key is written for the provider. Browser push
notifications are a separate opt-in governed by the browser's notification permission and the
Notifications module, never by these switches. The general rules, the operator allow-list and the
replay limits are in [monitoring-and-analytics.md](monitoring-and-analytics.md).

Every value entered here is a **public** identifier (a site id, a public ingest key, a web app id). Never
paste a secret, token or service-account file: the settings screen refuses unknown fields and the public
config endpoint returns only these public values. Changes are audited as `analytics.telemetry_updated`
(field names only, never the identifiers).

| Provider | Purpose (consent) | What you enter | What it collects | How to enable |
| --- | --- | --- | --- | --- |
| Plausible | Usage analytics | Domain; optional approved origin | Page views by route template, empty referrer | Pick it as Page analytics; self-hosted origins must be in `WEB_TELEMETRY_ALLOWED_ORIGINS` |
| Umami | Usage analytics | Website UUID and an approved HTTPS origin | Page views by route template | Pick Umami; add its origin to `WEB_TELEMETRY_ALLOWED_ORIGINS` |
| GA4 | Usage analytics | `G-...` measurement id | One sanitized page view per route; Google signals and ad personalization off | Pick GA4; allow `https://www.googletagmanager.com` and the Google collection origins |
| Firebase Analytics | Usage analytics | Firebase web config and the `G-...` measurement id | Same GA4 property; sanitized page views only | Pick Firebase; fill the Firebase web config (choose GA4 or Firebase, not both) |
| PostHog | Usage analytics and/or Session replay | `phc_` project key; optional approved origin | Sanitized page views; replay only on the allowed public routes | Pick PostHog for pages and/or replay with the same project and origin |
| Microsoft Clarity | Session replay | Project id | Replay of the anonymous public `/about` page only, everything masked | Pick Clarity under Session replay |
| Sentry (browser) | Diagnostics and performance | Public DSN, sample rate | Errors and traces with scrubbed URLs; no request bodies or personal data | Switch on Sentry diagnostics and enter the public DSN |
| Firebase Performance | Diagnostics and performance | Firebase web config, sample rate | Manual, sanitized traces only | Switch on Firebase Performance and fill the Firebase web config |

Backend Sentry is a deployment setting (`SENTRY_DSN`, optional `SENTRY_TRACES_SAMPLE_RATE`): it sends
no default personal data, no request bodies, no local variables and runs a scrubber before every event.

## Content Security Policy

The web server's policy is built at start-up from the operator's `WEB_TELEMETRY_ALLOWED_ORIGINS` (comma
separated HTTPS origins) and the Plausible-compatible variables. It cannot follow a per-space setting,
so a provider that loads a vendor script or reports to a vendor host works only when the operator has
listed that vendor's origins; the setting alone never widens the policy. Leave the list empty to keep
the strict default.

## Replay rules

Replay is allowed only on anonymous public routes: Clarity on `/about`, PostHog on `/about` and the
listed public inventory, events, shop and bookings pages. Staff, finance, sign-in and every
authenticated or unknown route stay excluded, and crossing into one reloads the page. Inputs and text
are masked, images, video, canvas and frames are blocked, and network bodies and headers are never
recorded.

## Withdrawal

Visitors can withdraw a purpose at any time and the provider stops at once. Withdrawal cannot delete
what the provider already holds; use the provider's own deletion and retention tools.

## Testing without accounts

None of the providers needs a real account to test SpaceWorks' side. Use fake ids; the application never
sees a vendor secret.

**Proven offline** (`frontend/src/lib/telemetry/providerMatrix.test.ts`, run with
`npx vitest run src/lib/telemetry --pool=forks --maxWorkers=1`): for Plausible, Umami, GA4, Firebase
Analytics, PostHog, Clarity, Sentry and Firebase Performance, with fake config:
no loader, script, network call or cookie before consent (and none when only a different purpose is
granted); after consent the adapter is loaded with exactly the configured id/origin; withdrawal stops the
adapter; replay never starts outside the anonymous public routes. Already covered elsewhere:
`providers.test.ts` (PostHog analytics/replay coalescing and project isolation, unsafe-origin refusal, legacy
fallback), `controller.test.ts` (no import without consent, revoked scope, tenant/config consent scoping),
`adapters.test.ts` (GA4 fixed host, automatic pageviews off, opt-out preserved; Plausible and Clarity after
cancellation), `adapters/sentry.test.ts` (scrubbing), `replayRoutes.test.ts`, `runtime.test.ts`,
`sessionFence.test.ts`.

**Pointing a provider at a local collector.** The browser loads each vendor's script from the origin you
configure, so a stand-in server can record what would be sent:

1. Start any local HTTPS-capable echo/collector (for example `npx http-server --ssl` with a self-signed
   certificate you trust, or a tiny script that logs every request line and body to a file).
2. For **Plausible**, **Umami** and **PostHog** enter its origin as the endpoint (a bare `https://` origin;
   the settings screen and the client both reject paths and credentials) and add the origin to
   `WEB_TELEMETRY_ALLOWED_ORIGINS` so the Content Security Policy permits it. Serve a stub `script.js` /
   `js/script.js` that defines the tracker function, or simply watch for the request.
3. **GA4**, **Firebase**, **Clarity** and **Sentry** use fixed vendor hosts. Test them by letting the browser
   request the real script host with a fake id (it will reject the id, which is fine) and checking in the
   network panel that nothing is requested before consent, and by blocking the host to confirm the page
   still works.
4. Grant and withdraw consent in the Privacy preferences box and watch the collector: requests start only
   after consent and stop on withdrawal; the URLs carry route templates, never raw ids.

**Only a real account can prove:** that the vendor accepts the id and shows data, vendor-side retention and
deletion, Sentry event ingestion and source-map handling, GA4/Clarity/PostHog dashboards and privacy
settings (masking, automatic capture off), and that your operator allow-list covers every host the vendor
actually uses in production.
