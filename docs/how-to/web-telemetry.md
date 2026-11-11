---
title: Add web analytics, replay and error tracking per space
group: How-to guides
order: 140
summary: Configure Plausible, Umami, GA4, PostHog, Clarity or Sentry for one space, with visitor consent.
---

# Add web analytics, replay and error tracking per space

Every web telemetry provider is **off** until two things are true: a Space Manager has configured it, and the visitor has agreed to that provider's purpose in the privacy preferences box. Until then no script loads, no request is sent and nothing is stored in the browser.

## Before you start

- You are a Space Manager (or, for the central site, the platform superadmin).
- You have a project at the provider. Use only **public** identifiers; the settings screen refuses unknown fields and never accepts secrets.
- Self-hosted servers: you control the Content Security Policy (below).

## Steps

1. Open **Insights > Analytics > Web telemetry**.
2. Pick a provider for each purpose:

| Provider | Purpose | You enter |
| --- | --- | --- |
| Plausible | Usage analytics | Domain; optional approved origin |
| Umami | Usage analytics | Website UUID and an approved HTTPS origin |
| GA4 | Usage analytics | `G-...` measurement id |
| Firebase Analytics | Usage analytics | Firebase web config and the `G-...` id (choose GA4 or Firebase, not both) |
| PostHog | Usage analytics and/or replay | `phc_` project key; optional approved origin |
| Microsoft Clarity | Session replay | Project id |
| Sentry (browser) | Errors and performance | Public DSN and sample rate |
| Firebase Performance | Performance | Firebase web config, sample rate |

3. Save. Changes are audited as `analytics.telemetry_updated` (field names only).

## Allow the provider's hosts (self-hosted)

The website's Content Security Policy is built at start-up from `WEB_TELEMETRY_ALLOWED_ORIGINS`, a comma-separated list of HTTPS origins. A provider that loads a vendor script or reports to a vendor host works only if you list its origins, so the setting alone never widens the policy. Set the same value on the website container and the backend, then restart:

```env
WEB_TELEMETRY_ALLOWED_ORIGINS=https://analytics.example.org,https://www.googletagmanager.com
```

Leave it empty to keep the strict default.

## What visitors see

Visitors choose per purpose (usage analytics, session replay, diagnostics) in the privacy preferences box and can withdraw at any time; the provider stops at once. Replay runs only on anonymous public routes, with inputs and text masked. Staff, finance and sign-in pages are always excluded.

> **Warning** Withdrawal stops sending but cannot delete what a provider already holds. Use the provider's own deletion tools.

## Test without real accounts

Use fake ids and watch the browser's network panel: nothing is requested before consent, requests start after consent and stop on withdrawal, and URLs carry route templates, never raw ids.

## See also

- [Web telemetry providers](../web-telemetry-providers.md) and [Monitoring and analytics](../monitoring-and-analytics.md)
