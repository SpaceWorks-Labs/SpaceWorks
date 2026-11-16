---
title: Contributing
group: Project
order: 40
summary: How to set up a development stack, run the tests, follow the code conventions and get a change merged.
---

# Contributing

Thanks for helping. This page is the short route; the repository's `.github/CONTRIBUTING.md` and
`.github/DEVELOPMENT.md` carry the full text.

## Set up

Fork and clone `https://github.com/SpaceWorks-Labs/SpaceWorks`. The easiest way to run everything is the
single development script, which runs the whole stack in Docker with live reload and nothing installed on
your host:

```bash
./scripts/dev.sh up --build       # backend, frontend, database, Redis, storage, worker
./scripts/dev.sh test             # isolated backend tests (default arguments: -q)
./scripts/dev.sh e2e              # Playwright browser tests against the running dev stack
```

The public catalogue is at `http://localhost:5000/m/makerspace`, and the API is at
`http://localhost:8000/api` with Swagger at `/docs/`, ReDoc at `/redoc/` and the schema at `/schema/`.

To run the parts directly instead, you need Python 3.12 or newer and Node 20.19+ or 22.12+: a PostgreSQL
database (`docker compose up -d db`), then `pip install -r requirements.txt`, `python manage.py migrate`,
`python manage.py seed_demo` and `python manage.py runserver` in `backend/`, and `npm install` and `npm run dev`
in `frontend/`.

## Tests

- Backend tests live in `backend/tests/<app>/`, written with pytest. Test external behaviour, not
  implementation.
- Each `dev.sh test` run provisions its own disposable PostgreSQL, Redis and object storage. Never run two
  pytest processes against one database.
- Frontend unit tests use Vitest; browser tests use Playwright.
- **Tests are committed and never deleted.** A test for something out of scope for a release is skipped, not
  removed. The only baseline is zero failures: any red test is a new regression.
- Continuous integration runs checks (frontend build and lint, backend checks, API contracts, repository
  rules), not the full test suites, so run the relevant tests locally before pushing.

## Code conventions

- **Small files.** Aim for about 200 lines and never exceed about 300, with one responsibility per file. When a
  file outgrows that, split it into sibling modules and keep the original as a thin re-export. The rules check
  (`python scripts/ci/check_rules.py`) enforces this.
- **Document every API route in OpenAPI.** Each route needs a drf-spectacular entry with request and response
  schemas, authentication and error responses. An undocumented endpoint is incomplete. Regenerate
  `frontend/openapi-schema.json` and `frontend/src/generated/api.ts` when routes or models change.
- **Audit every state change.** Every state-changing endpoint records an audit entry through the audit
  service. Audit logs are append-only.
- **Scope every query to a makerspace** through the access-control module. Forgetting this is a cross-tenant
  leak, not just a bug.
- **One source of truth for transitions and quantities.** Request status changes only through the request
  workflow service, and stock counts only through the inventory availability module.
- **Evidence is immutable.** Evidence photo records and QR scan records are never edited or deleted.
- **Translate every user-facing string.** Mark text with Lingui's `t` macro in the frontend and Django's
  translation functions in the backend, and run the literal checks. See [Translating Space
  Works](../i18n.md).
- **Production quality.** Validate input at the boundary, handle outside-service failure explicitly, log in
  a structured way and return consistent typed errors. No placeholder authorization.
- **Chain migrations off the real latest migration** of the app, not the number someone quoted.

## Branches and pull requests

1. Start from the latest `dev` and make a branch such as `feature/<slug>` or `fix/<slug>`. Do not work
   directly on `dev` or `main`.
2. Use clear conventional commit subjects (`feat(inventory): ...`, `fix(printing): ...`, `docs: ...`), one line.
3. Keep each pull request to a single concern, and update the docs alongside the code.
4. Open the pull request against **`dev`**, describing what changed and why, and call out environment
   variables, migrations or manual steps.
5. Only the maintainer merges into `main`, which publishes a release. See [Release process](release-process.md).

## Licensing of contributions

No CLA is required. Your contribution is offered under AGPL-3.0-or-later, and you keep the copyright. See
[License](license.md). To report a security problem, follow the [security policy](security-policy.md) instead
of opening a public issue.
