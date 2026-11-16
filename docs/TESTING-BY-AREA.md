# Testing by area

Area selection is an iteration tool; the full backend, frontend and end-to-end runs remain the release gate.
`backend/tests/areas.py` owns backend area names, test-path globs, app ownership, frontend-feature ownership for
affected selection, and dependency expansion. Module areas are derived from `makerspaces/module_registry*.py`.
`frontend/src/test/areas.ts` maps those same names to Vitest directory filters. A drift guard compares the names.

## Run locally

```bash
python backend/tests/areas.py --list
./scripts/dev.sh test --area events
./scripts/dev.sh test --area events --area bookings
./scripts/dev.sh test --area events -m 'not migration' -q
./scripts/dev.sh test --area-affected HEAD~1
./scripts/dev.sh test --area bookings --area-affected release/base

cd frontend
npm run test:area -- events
npm run test:area -- events bookings --maxWorkers=2
npm run test:area -- --list
```

The backend runner needs host Python and the existing Bash/Docker prerequisites. Frontend area runs need
Node 22+ and installed frontend dependencies, matching CI. No extra package is required.

Repeated explicit areas become `-m 'area_bookings or area_events'`. An existing `-m` expression is ANDed
with that selection. Tests can have several markers; pytest runs each selected case once. Without area flags,
the runner passes arguments through as before, including the existing default and `TEST_ENTRYPOINT` behavior.
Area flags require the pytest entrypoint.

`--area-affected REF` reads tracked changes against the given ref, including staged and unstaged changes. It
maps `backend/apps/<app>/...`, existing backend test files, and `frontend/src/features/<feature>/...` to areas.
It then follows `requires_modules` in both directions, transitively: changing `events` also selects
`event_reimbursements`; changing `mobile` reaches `member_accounts` and `membership`. Shared files, an unknown
app/feature, registry changes, or a deleted/unclassified test select the full suite. An empty diff starts no
infrastructure. Explicit areas are unioned with affected areas. Unknown area names or invalid refs fail before
the test infrastructure starts. New untracked files need an explicit area or a full run.

After collection, the backend prints selected **test-case** counts for every area. For a static file inventory:

```bash
./scripts/dev.sh test tests/test_areas.py::test_print_area_file_counts -s
```

Counts overlap intentionally. App imports give conservative coverage where several modules share one app.
For example, changes to `integrations` select all its channel areas. Selection still collects the suite before
pytest deselects cases; it saves test execution and does not isolate imports or database setup.

## Area names

Core areas are permanent; absence of a module switch is intentional.

| Area | Scope |
| --- | --- |
| `auth` | Authentication, MFA, staff identity, RBAC, API clients |
| `tenancy` | Tenant scoping, RLS, encryption, deployment separability |
| `inventory` | Stock availability, assets, folded repair/maintenance/procurement capabilities |
| `lending` | Request workflow, direct loans, evidence, QR scans and boxes |
| `audit` | Append-only audit history and attestation |
| `payments_ledger` | Debts, pricing, receipts, settlements and finance history |
| `data_export` | Tenant and member export |
| `backup` | Deployment/space archives and restore |
| `tenant_migration` | Portable capture, import and cutover |
| `platform` | Control plane, hosting, space controls and operational tooling |
| `api_contract` | OpenAPI, contract guards and test-area infrastructure |
| `frontend_shell` | Shared UI, routing, permissions, localization and public shell |
| `organizations` | Organization governance and delegated authority |
| `forms` | Shared form schemas and answer validation |

Every current registry key also has its own area:

| Registry areas | Purpose |
| --- | --- |
| `public_inventory`, `request_workflow`, `staff_admin`, `scanner`, `evidence_uploads`, `qr_management` | Structural core module keys; cannot be uninstalled |
| `guest_handover`, `bulk_import`, `containers`, `stock_transfers`, `stocktake`, `qr_print_batches`, `asset_units` | Optional inventory and handover surfaces |
| `machines`, `machine_service` | Machine management and service jobs, including the retired print queue |
| `events`, `event_reimbursements`, `bookings` | Events, event support and resource bookings |
| `membership`, `member_accounts`, `mobile`, `presence` | Community, account, device-session and presence surfaces |
| `notifications`, `email`, `telegram`, `sms`, `whatsapp`, `slack`, `mattermost`, `discord`, `webhook` | Inbox and delivery channels |
| `payments` | Optional online payment rail (`payments_rail` app); ledger remains core |
| `devices`, `shop`, `reports`, `analytics` | Device enrollment, shop, report exports and analytics |

`maintenance`, `procurement`, `warranty` and `printing` are not new module-area names. Their tests belong to
the owning inventory/machine/booking or machine-service areas. `backup` is a core area, not a revived module.

## CI

In GitHub Actions, open **Tests → Run workflow**, choose the branch and enter `events bookings` or
`events,bookings` in **areas**. A supplied value runs one job containing selected backend cases, the matching
cases in the separate tombstone deployment profile, and selected frontend tests. Backend migration cases are
included unless explicitly filtered locally. An empty tombstone selection is allowed; actual failures are not.
Shell/platform/API-contract selections also run the existing Node website/documentation contract suites.
Leaving **areas** empty preserves all existing full-suite jobs. Pull requests and pushes retain full runs.

## Add or change tests

1. Put backend tests in `backend/tests/<app>/` and frontend tests beside their component/service.
2. Use real app imports. Backend ownership unions path globs, app imports, literal module/capability keys and
   imported test helpers. Helpers are parsed with Python AST; collection does not execute them for tagging.
3. Parametrized switch/interconnection cases should carry their module or feature keys as parameters, including
   tuples/dictionaries for pairs. Collection adds all the corresponding markers, including feature parents.
4. For a new purpose-based test directory or a static tooling test, add an explicit path glob in `areas.py`.
   There is no catch-all owner for an unknown test file. `test_every_backend_test_file_has_an_area` checks the
   entire test tree even during a targeted run.
5. New registry keys automatically create backend areas. Register the matching marker in `backend/pytest.ini`,
   add its frontend directory mapping, and update this area list. Drift guards reject missing registrations.

## Switch and interconnection coverage

Keep primary workflow tests in their domain folders. Shared module combinations remain in `tests/modules/`;
they receive every area they exercise. Existing `test_switch_matrix_*`, `test_offstate_*`, family and flow-audit
suites remain in place, including their route, money, notification and retained-data scenarios.

The fast `tests/modules/test_area_gate_contracts.py` matrix adds exact 404/error-key contracts for every
optional module and live capability, off/on restoration, feature-to-module and feature-to-feature dependencies,
tenant-local switches and refusal to uninstall structural core keys. It uses unsaved Django models and no URL
crawl. `test_area_switch_retention.py` uses the real install/uninstall services for every optional key, with
persisted stock, a loan and an unclaimed ledger charge; it asserts identical retained rows and one capability
audit per change, including retries. These protect shared boundaries; they do not replace domain workflow tests.

For each changed flow, add on/off/on cases that assert its exact status and error code, persisted data retained,
and both sides of connected-module switches. Include relevant permission, tenancy, evidence, money, time,
retry/concurrency and external-failure conditions. A filename, marker or count alone is not proof of a condition.
Non-toggleable core areas need tests against the optional modules they consume, rather than artificial core
switches. Frontend area runs always include shared shell, gate, permission and component tests.
