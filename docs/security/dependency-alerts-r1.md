# Dependency security alerts — release 1

Production gate item for release 1 (owner decisions #81 and #88). This page records every open
Dependabot alert on `SpaceWorks-Labs/SpaceWorks` as of 2026-10-28, what was done about it, and any
risk still carried. It feeds the release security summary (#121e).

**Source:** `gh api repos/SpaceWorks-Labs/SpaceWorks/dependabot/alerts?state=open` — 25 alerts
(8 high, 13 medium, 4 low), all npm, all in `frontend/package-lock.json`. Dependabot reported no
Python, Docker or GitHub Actions alerts.

**Rule applied:** the smallest safe bump — the first patched version inside the current major.
Nothing crossed a major version.

## Fixed

| # | Severity | Package | Relationship | Advisory | Vulnerable | From → To |
|---|---|---|---|---|---|---|
| 3 | high | postcss | direct (dev) | GHSA-r28c-9q8g-f849 | ≤ 8.5.17 | 8.5.16 → 8.5.23 |
| 4 | medium | postcss | direct (dev) | GHSA-fxqj-rqcc-2cmp | ≤ 8.5.22 | 8.5.16 → 8.5.23 |
| 5 | high | undici | transitive (jsdom, dev) | GHSA-4cwx-7wf7-3272 | < 7.29.0 | 7.28.0 → 7.30.1 |
| 6 | medium | undici | transitive (jsdom, dev) | GHSA-8xcm-r25x-g524 | < 7.29.0 | 7.28.0 → 7.30.1 |
| 7 | medium | undici | transitive (jsdom, dev) | GHSA-v3r7-h72x-cjcm | < 7.29.0 | 7.28.0 → 7.30.1 |
| 8 | medium | undici | transitive (jsdom, dev) | GHSA-jr45-8vmc-qm54 | < 7.29.0 | 7.28.0 → 7.30.1 |
| 9 | medium | undici | transitive (jsdom, dev) | GHSA-m8rv-5g2x-5cg5 | < 7.29.0 | 7.28.0 → 7.30.1 |
| 10 | high | react-router | transitive (react-router-dom) | GHSA-qwww-vcr4-c8h2 | 7.12.0 – < 7.18.2 | 7.18.1 → 7.18.2 |
| 13 | medium | @vitest/mocker | transitive (vitest, dev) | GHSA-82fw-gwwq-j7x9 | < 4.1.11 | 4.1.10 → 4.1.12 |
| 14 | medium | vitest | direct (dev) | GHSA-82fw-gwwq-j7x9 | < 4.1.11 | 4.1.10 → 4.1.12 |
| 17 | low | undici | transitive (jsdom, dev) | GHSA-8436-99hf-9mmv | < 7.29.1 | 7.28.0 → 7.30.1 |
| 18 | high | undici | transitive (jsdom, dev) | GHSA-w293-vg96-wgc3 | 7.24.1 – < 7.29.1 | 7.28.0 → 7.30.1 |
| 19 | low | undici | transitive (jsdom, dev) | GHSA-2gqq-gqf2-x968 | < 7.29.1 | 7.28.0 → 7.30.1 |
| 20 | medium | undici | transitive (jsdom, dev) | GHSA-2jfj-6hjv-fm6j | < 7.29.1 | 7.28.0 → 7.30.1 |
| 23 | low | undici | transitive (jsdom, dev) | GHSA-r53p-7pc4-xj5r | < 7.29.1 | 7.28.0 → 7.30.1 |
| 24 | medium | undici | transitive (jsdom, dev) | GHSA-pmjh-fq2x-6v4x | 7.11.0 – < 7.29.1 | 7.28.0 → 7.30.1 |
| 25 | high | source-map-js | transitive (postcss, css-tree; dev) | GHSA-68fv-2mgg-jv7q | < 1.2.2 | 1.2.1 → 1.2.2 |
| 26 | medium | vite | direct (dev) | GHSA-698v-4r3x-3vcv | 8.0.0 – 8.1.5 | 8.1.3 → 8.1.6 |
| 27 | high | vite | direct (dev) | GHSA-587h-7wmj-h5pm | 8.0.0 – 8.1.5 | 8.1.3 → 8.1.6 |
| 28 | medium | vite | direct (dev) | GHSA-r825-w8mm-5pxw | 8.0.0 – 8.1.5 | 8.1.3 → 8.1.6 |
| 29 | medium | vite | direct (dev) | GHSA-rq7h-c2jc-7f22 | 8.0.0 – 8.1.5 | 8.1.3 → 8.1.6 |
| 30 | low | vite | direct (dev) | GHSA-9jrq-w75r-8gcw | 8.0.0 – 8.1.5 | 8.1.3 → 8.1.6 |
| 31 | medium | @vitest/mocker | transitive (vitest, dev) | GHSA-qxg6-89mg-rqv8 | < 4.1.12 | 4.1.10 → 4.1.12 |

Notes:

- `undici` and `source-map-js` were raised with `npm update` inside their parents' existing ranges
  (jsdom `^7.25.0`, postcss `^1.2.1`), so no `overrides` entry was needed. `npm update` took undici
  to 7.30.1, the newest 7.x, rather than the minimum 7.29.1; it is still inside the same major.
- Everything except `react-router` is a build or test tool and never ships in the browser bundle.
  The react-router advisory concerns RSC mode, which this app does not use; it was patched anyway.
- Lockfile side effects of the vite bump: rolldown 1.1.4 → 1.1.5 and its platform bindings,
  `@oxc-project/types`, `@napi-rs/wasm-runtime`, `nanoid`, `chai`, `tinyrainbow`, `set-cookie-parser`.
  All are patch or minor moves.

## Open — owner decision required

| # | Severity | Package | Advisory | Vulnerable | Status |
|---|---|---|---|---|---|
| 1 | high | xlsx 0.18.5 (runtime) | GHSA-4r6h-8v6p-xvw6 — prototype pollution | < 0.19.3 | **No patched version on npm** |
| 2 | high | xlsx 0.18.5 (runtime) | GHSA-5pgg-2g8v-p4x9 — ReDoS | < 0.20.2 | **No patched version on npm** |

SheetJS stopped publishing to the npm registry at 0.18.5; fixed builds (0.20.2+) are published only
on `cdn.sheetjs.com`. In this app `xlsx` is used in one place: the staff Bulk Import panel parses a
`.xlsx` file the staff member picks (`frontend/src/features/staff/panels/BulkImportHelpers.ts`,
lazy-loaded). The exposure is a crafted spreadsheet opened by an authenticated staff member, in that
staff member's own browser tab: the worst outcomes are a frozen tab (ReDoS) or a polluted object
prototype in that tab. Nothing is parsed server-side by this library.

Options for the owner:

1. **Switch to the vendor build** — `"xlsx": "https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz"`.
   Same API, fixes both advisories. Cost: a non-registry tarball in the lockfile, which Dependabot
   and `npm audit` cannot track afterwards.
2. **Parse on the server** — the backend already ships `openpyxl`; add an endpoint that returns the
   first sheet's rows and drop `xlsx` from the frontend. Removes the dependency; costs an endpoint
   (Swagger, rbac scoping, audit not needed for a read-only parse) and an upload round trip.
3. **Accept the risk for release 1** — staff-only input, client-side only, no server impact; dismiss
   the two alerts with that reason and revisit in release 2.

## Not a Dependabot alert, but found by `pip-audit`

`.github/workflows/security-audit.yml` runs `pip-audit -r backend/requirements.txt` on every pull
request and is enforcing. It currently reports three advisories against **cryptography 48.0.1**:

| Advisory | Summary | Fixed in | Reachable here? |
|---|---|---|---|
| PYSEC-2026-3552 / GHSA-g6cj-pr64-35w5 | PKCS#7 EnvelopedData decryption Bleichenbacher oracle | 50.0.0 | No — the backend never decrypts PKCS#7 |
| PYSEC-2026-3553 / GHSA-jwv3-5hgf-82ww | Exponential path building with duplicate self-signed intermediates | 49.0.0 | No — `x509.verification` is not used |
| PYSEC-2026-3554 / GHSA-m2h6-j472-rp4c | Wildcard DNS names escape `permittedSubtrees` | 49.0.0 | No — `x509.verification` is not used |

`requirements.txt` asks for `cryptography>=44`, but the resolver cannot go past 48.x:
`django-anymail[amazon-ses]==15.2` pulls in `amazon-s3-encryption-client-python` 4.0.0 (its only
release), which requires `cryptography>=48.0.0,<49`. That client is imported only by anymail's
**inbound** SES webhook (`anymail/webhooks/amazon_ses.py`), which this project does not route; the
SES sending backend needs only `boto3`, already a direct requirement. This is an owner question
(see the lane report): drop the `[amazon-ses]` extra and require `cryptography>=50`, or accept the
risk with `--ignore-vuln` entries in the workflow.

## Also in this change

`drf-spectacular` is pinned to `==0.30.0` (the version already resolved), so the CI `contracts`
job, which diffs a freshly generated schema against `frontend/openapi-schema.json`, cannot go red
on an upstream release with no code change.

## Verification (2026-10-28, lane/p2-deps)

- Frontend: `npx tsc -b` clean; `npm run build` passes, including the PWA verify script; the full
  vitest suite passes (577 files, 2735 tests). `npm audit` reports only `xlsx`.
- Backend (python:3.12-slim, worktree mounted read-only, throwaway keys): `pip install -r
  requirements.txt` resolves the same set as before the pin; `manage.py check` reports no issues;
  `makemigrations --check --dry-run` reports no changes; the regenerated OpenAPI schema is
  byte-identical to `frontend/openapi-schema.json`. `pip freeze` is identical before and after the
  pin, so no backend package changed version and no backend pytest run was needed for this change.
- `scripts/ci/check_rules.py`: the CLAUDE.md/AGENTS.md twin rule passes; the 300-line ceiling rule
  fails on the seven pre-existing offenders the P2 split sweep owns. None is touched here.
