# Dependency security alerts — release 1

Production gate item for release 1 (owner decisions #81 and #88). This page records every open
Dependabot alert on `SpaceWorks-Labs/SpaceWorks` as of 2026-10-28, what was done about it, and any
risk still carried. It feeds the release security summary (#121e).

**Source:** `gh api repos/SpaceWorks-Labs/SpaceWorks/dependabot/alerts?state=open` — 25 alerts
(8 high, 13 medium, 4 low), all npm, all in `frontend/package-lock.json`. Dependabot reported no
Python, Docker or GitHub Actions alerts.

**Rule applied:** the smallest safe bump — the first patched version inside the current major.
No npm package crossed a major version. The two exceptions were decided by the owner (#123): `xlsx`
was removed, and cryptography went 48 → 50.

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

## Resolved by owner decision #123

### xlsx (alerts #1 and #2) — package removed

| # | Severity | Package | Advisory | Vulnerable | Fix |
|---|---|---|---|---|---|
| 1 | high | xlsx 0.18.5 (runtime) | GHSA-4r6h-8v6p-xvw6 — prototype pollution | < 0.19.3 | Removed; parsing moved to the server |
| 2 | high | xlsx 0.18.5 (runtime) | GHSA-5pgg-2g8v-p4x9 — ReDoS | < 0.20.2 | Removed; parsing moved to the server |

SheetJS stopped publishing to npm at 0.18.5, so no in-registry fix existed. Its only use was the staff
Bulk Import panel reading a picked `.xlsx` to show its columns for matching. The owner chose option (b),
parse on the server:

- `POST /api/v1/admin/makerspace/{id}/inventory/import/sheet` (`apps/admin_api/views_bulk_sheet.py`,
  `bulk_import_sheet.py`) takes the upload and returns `{"rows": [...]}`, one object per non-blank row
  keyed by the first row's headers with blank cells as `""` — the shape SheetJS produced — so the
  panel's upload → match columns → preview → import flow is unchanged.
- Same gate as the rest of Bulk Import: the `bulk_import` module and `EDIT_INVENTORY` in that
  makerspace, through rbac. Each read writes an `inventory.bulk_import_sheet_read` audit row (row and
  column counts only, no file name or cell content). Nothing is stored.
- Safe parsing: openpyxl `read_only=True, data_only=True, keep_links=False`, so formulas are never
  evaluated (only cached values are read) and external links are not loaded; the existing 5 MB and
  5,000-row caps plus a new 100-column cap, applied while streaming; the first sheet in tab order, as
  the browser parser used. A corrupt file is a 400, not a 500.
- `xlsx` and its 8 transitive packages are gone from `frontend/package.json` and the lockfile;
  `npm audit` reports 0 vulnerabilities.

Columns with a blank header are dropped from the returned rows (SheetJS named them `__EMPTY`); they
could not be matched to a field meaningfully either way.

### cryptography 48.0.1 (found by `pip-audit`, not Dependabot) — raised to 50.0.2

`.github/workflows/security-audit.yml` runs an enforcing `pip-audit -r backend/requirements.txt` on
every pull request. It reported three advisories against cryptography 48.0.1:

| Advisory | Summary | Fixed in | Reachable here? |
|---|---|---|---|
| PYSEC-2026-3552 / GHSA-g6cj-pr64-35w5 | PKCS#7 EnvelopedData decryption Bleichenbacher oracle | 50.0.0 | No — the backend never decrypts PKCS#7 |
| PYSEC-2026-3553 / GHSA-jwv3-5hgf-82ww | Exponential path building with duplicate self-signed intermediates | 49.0.0 | No — `x509.verification` is not used |
| PYSEC-2026-3554 / GHSA-m2h6-j472-rp4c | Wildcard DNS names escape `permittedSubtrees` | 49.0.0 | No — `x509.verification` is not used |

The resolver could not pass 48.x because `django-anymail[amazon-ses]==15.2` pulled in
`amazon-s3-encryption-client-python` 4.0.0 (its only release), which requires `cryptography<49`. That
client is imported only by anymail's inbound SES webhook, which this project does not route; SES
sending needs only `boto3`, already a direct requirement. Per the owner (option a), the requirement is
now plain `django-anymail==15.2` with `cryptography>=50`; it resolves to cryptography 50.0.2, and
`amazon-s3-encryption-client-python` drops out. No other package changed version (pytest moved
9.1.1 → 9.2.0 between runs because of an upstream release under the existing `pytest>=9`).

## Also in this change

`drf-spectacular` is pinned to `==0.30.0` (the version already resolved), so the CI `contracts`
job, which diffs a freshly generated schema against `frontend/openapi-schema.json`, cannot go red
on an upstream release with no code change.

## Verification (2026-10-28, lane/p2-deps)

- Frontend: `npx tsc -b` is clean; `npm run build` passes, including the PWA verify script; the full
  vitest suite passes (577 files, 2737 tests, including two new Bulk Import cases for the server-read
  `.xlsx` path and its error message). `npm audit` reports 0 vulnerabilities.
- Backend (python:3.12-slim, worktree mounted read-only, CI environment and throwaway keys):
  `pip install -r requirements.txt` resolves cryptography 50.0.2 and no
  `amazon-s3-encryption-client-python`; `pip-audit -r requirements.txt` finds no known
  vulnerabilities; `manage.py check` reports no issues; `makemigrations --check --dry-run` reports no
  changes. An SES send through the project's own transport (`mail_providers/ses.py`) against a stubbed
  sesv2 endpoint succeeds. The regenerated OpenAPI schema differs from the snapshot only by the new
  `/inventory/import/sheet` path and its two schemas; the snapshot and `api.ts` are regenerated by the
  coordinator at merge.
- Targeted pytest through the shared test queue (owner decision #125: changed areas only), all green:
  the new spreadsheet-endpoint tests (11: happy path, first sheet only, formulas not evaluated, audit
  row, no EDIT_INVENTORY, other tenant, anonymous, module off, malformed file, non-xlsx, size, row and
  column limits); Bulk Import hardening, the inventory module off-state matrix, the delegated-route
  catalogue, audit presentation, SES/email provider transports and config, strict mail (135 more);
  the Bulk Import cases in `test_admin_api.py` (15); encryption (crypto, keys, brokers, rotation,
  blind index, checks) and App Attest/attestation (80).
- `scripts/ci/check_rules.py`: the CLAUDE.md/AGENTS.md twin rule passes; the 300-line ceiling rule
  fails only on the seven pre-existing offenders the P2 split sweep owns. None is touched here.
