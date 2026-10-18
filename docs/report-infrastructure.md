# Phase 1f-0 report infrastructure handoff

This phase adds no report builders or report keys. The existing 43-key registry remains the
composition point. Tenant previews, downloads and scheduled artifacts share an output allowlist;
organization calculations retain internal denominator fields until their final public projection.
The existing holder reports (`top-borrowers`, `active-loans`, `returns`) are now explicitly
identity-bearing, tenant-only and unschedulable.

## Builder lane extension points

1. **Registration:** define a tuple in `backend/apps/operations/report_definitions_<area>.py`,
   import it in `report_registry.py`, and expand it into `REPORT_DEFINITIONS`. Extend existing
   definitions for existing keys. Set `fields`, real source-module gates, the report's staff
   action, grains and version. The registry declares `makerspace_id` among allowed fields for
   deployment-capable definitions; tenant builders can omit that column. Declare every public
   field, including summary fields. Unknown output fields are dropped with a structured warning.
2. **Privacy:** `identity_bearing=True` requires `deployment_aggregate=False`,
   `schedulable=False` and an entry in `org_report_scope.EXCLUDED_ORGANIZATION_REPORT_KEYS`.
   `platform_only=True` requires `deployment_aggregate=True` and `schedulable=False`.
   Registry lookups and the `operations.E005` Django check validate these declarations.
3. **Platform builders:** accept `platform_context` and call
   `platform_scope.require_platform_context(platform_context)` before reading data, including
   when the builder is imported directly. Registry-dispatched builders additionally enforce
   that context. Only superadmin aggregate/platform views mint it using the private view factory.
   Use `platform_analytics_spaces(ctx)` for analytics; this delegates to
   `platform_dashboard.platform_spaces()` and excludes hidden tenants regardless of membership.
   Tenant-local views use `tenant_local_hidden_block_applies(actor, makerspace, action)`.
4. **Anonymous service counts:** only `platform-services` may call
   `hidden_platform_service_bucket(ctx, rows, report_key=...)`. Internal input rows contain
   `makerspace_id`, `provider_source`, `service`, `day` (a date), and nonnegative integer `count`.
   Supported services: `email`, `push`, `sms`, `whatsapp`, `attestation`, `connect`, `backups`.
   The helper ignores own providers and visible spaces, then emits only service/day/bucket/count.
   It must never be used for business activity, own-provider usage, adoption or growth.
5. **Organization combination:** declare the matching `org_report_strategies.STRATEGIES` entry
   and call `org_report_aggregate.register_combine(report_key, combine)` from the area's
   registration module. The function signature is `combine(rows_by_space, *, limit)` and it
   returns a list of dictionaries. Each input item is `(makerspace_id, list_of_records)`;
   all source rows and private calculation fields are available. Sum numerators and denominators
   before dividing; preserve period/currency/unit partitions. Only public declared fields leave
   orchestration. Percentile/median keys remain organization-excluded. Strategy field comparisons
   omit the infrastructure `makerspace_id` column.
6. **Grains:** advertise `week` in `definition.grains` when supported. Use
   `reports_common.period_expression(field, grain, makerspace=space)` for a tenant-local SQL
   calendar bucket, or `tzinfo=zone` for an explicitly resolved zone. ISO weeks start Monday.
   Organization views validate grain and orchestration forwards it only to grain-aware builders.
7. **Coverage and conditions:** update `report_coverage.REPORT_MODULE_COVERAGE` associations;
   the acceptance table is `report_coverage_contract.REPORT_COVERAGE_CONTRACT`.
   Grouped coverage associations do not create runtime dependencies. The coverage-only areas
   `presence`, `audit`, `organizations`, `platform` can have coverage entries but are not module
   gates. Add numeric threshold columns to `report_condition_metrics.NUMERIC_FIELDS`.
   Remove each completed key from `_PENDING_KEYS` in `test_grain_and_coverage_m1f0.py`.
   These are static strict xfails: completing a marked key produces XPASS until its mark is removed;
   regressions in completed keys fail normally.
8. **Disclosure tests:** use `tests.operations.report_assertions.assert_report_disclosure_safe`
   on JSON and decoded artifacts. Its default aggregate mode also refuses raw audit metadata,
   payloads, message bodies and feedback answers. Use `aggregate=False` only for intentional
   tenant-local subject exports. Builder metadata is a separate scalar allowlist in
   `report_output.META_FIELDS`; new measurement/provenance metadata must be declared there.

## Chart specification

The definition type permits `chart_spec=None`, but every previewable entry in the canonical
registry must now supply a valid spec. All these keys are required; referenced fields must appear
in the definition's output allowlist. `series` lists dimension fields; `values` is nonempty.

```json
{
  "series": ["source"],
  "x": {"field": "period", "kind": "time"},
  "values": [{"field": "count", "unit": "loans"}],
  "currency_field": null,
  "partition": "tenant",
  "negatives": "clip",
  "truncation": {"top_n": 5, "other_label": "Other"},
  "alt_template": "{count} loans in {period}"
}
```

`x.kind` is `time|category`; `partition` is `tenant|currency|unit|null`;
`negatives` is `allow|clip`. `truncation` can be null, otherwise `top_n` is a positive
integer and `other_label` is nonempty. `currency_field` can be null; currency partitioning
requires it. Tenant partitioning requires `makerspace_id`. Alt placeholders are plain declared
fields or `count`, with no attribute traversal, conversion or format expressions.
`report_validation.validate_chart_spec` enforces this; `serializers_report_chart.py` owns its
typed OpenAPI representation. Catalogs return `chart_spec` and `identity_bearing`.
Messaging analytics adds an optional `kind=line|stacked_bar` to individual values:
exclusive current outcomes stack, while cumulative counts and ratios remain lines.
All existing top-level F1 keys and values without a kind remain valid.

### Remaining chart coverage (1f-6)

`report_charts_remaining.py` closes the sixteen legacy/coverage/finance gaps plus the seven
previewable event/booking subject reports found by checking registry composition. The audit
trail definition also has a valid spec, while remaining CSV-only and non-previewable.
The F1 contract does **not** accept a `{"kind": "table"}` shortcut. Ledger charts use
existing collected/owed/refunded amounts, separated by effective status, row kind and refund
status; journal charts compare debit/credit by account. Both partition currency, use major
currency units and preserve negative values. Printer service charts hours; FabLab health
charts existing percentages because neither older shape declares a currency.

Active loans and returns expose `count=1` in each detail row (including exports), with
definition versions bumped to 2. Counts summarize only the returned rows. Event registrations,
feedback, booking reservations/answers and audit trail retain their version 1 export fields.
Their F1 table specs declare a category row dimension, empty `values` and no aggregation
settings; the client renders a table without summing IDs or adding synthetic columns.
FabLab health v2 includes `makerspace_id` in local rows
as well as aggregate rows, so its chart's x field exists in real output.

`GET /api/v1/admin/platform/analytics/{report_key}` returns the definition's `chart_spec`
alongside rows, typed rows and metadata for `platform-services` and `platform-usage`.
Those definitions already carried specs. `PlatformAnalyticsReportSerializer` documents
the required typed response field. Loan detail serializers document their count fields;
event and booking serializers keep their existing export allowlists.

SMS and WhatsApp have module-health coverage rows; communications-health v4 reads canonical
NotificationDelivery and original legacy mappings, with physical email and device-ledger outcomes
counted once. Held attempts/ingress, original abandonment history and proof-bound current consent
retain separate measurements. Module health/platform services are v3 and mobile reports v2. Module health retains its registered local export
fields and includes tenant identifiers only at deployment scope. Most-lent v2 preserves
undated legacy loans as a null period in unbounded reports instead of inventing an issue date;
dated windows naturally exclude those unknown timestamps.

The coverage acceptance table now associates `evidence-compliance` only with
`evidence_uploads`, and `import-quality` only with `bulk_import`. Both are explicitly
completed before coverage parametrization. `test_chart_spec_complete_m1f6.py` guards all
previewable definitions, currency safety, both platform responses for each grain, loan
row counts and the local health axis. Tests and generated OpenAPI/TypeScript regeneration
are left to the orchestrator for this lane; the repository ignores `backend/tests`, so
the new guard and the edited coverage test must be included explicitly at integration.

## Verification

- Focused database-free tests: **66 passed, 53 strict xfailed, 23 deselected**.
- Report/module system checks and organization strategy parity: passed for all 43 keys.
- Source parsing, whitespace checks, and the 300-line operations-module ceiling: passed.
- Spectacular generated the report schema with zero errors; its report-related changes and
  dependency schemas were applied while preserving unrelated pre-existing snapshot drift.
  TypeScript was regenerated from that snapshot.
- The 23 database tests cover tenant/org HTTP refusals, exports and scheduled artifacts,
  local-time SQL weeks, organization grain forwarding, and hidden buckets. They remain unrun:
  `scripts/dev.sh test` stopped before collection because sandbox access to Docker was denied.
  Run the four `test_*_m1f0.py` files through that isolated runner before integration.
- Independent delegated code review is clean. The separate Codex CLI review could not start
  because its app-server initialization was denied by the sandbox.
- Nothing was staged or committed. Tests are ignored by the repository's existing `.gitignore`.

## Files changed

Under `backend/apps/operations/`:

- `apps.py`
- `org_report_aggregate.py`
- `org_report_scope.py`
- `org_report_strategies.py`
- `org_reports.py`
- `platform_scope.py` (new)
- `report_coverage.py`
- `report_coverage_contract.py` (new)
- `report_definitions_existing.py`
- `report_download.py`
- `report_output.py` (new)
- `report_registry.py`
- `report_schedule_services.py`
- `report_types.py`
- `report_validation.py` (new)
- `reports.py`
- `reports_common.py`
- `serializers_report_catalog.py`
- `serializers_report_chart.py` (new)
- `serializers_report_schedules.py`
- `views_org_reports.py`
- `views_report_helpers.py`
- `views_report_schedules.py`
- `views_reports.py`

Under `backend/tests/operations/` (locally ignored):

- `report_assertions.py` (new)
- `test_definition_contract_m1f0.py` (new)
- `test_grain_and_coverage_m1f0.py` (new)
- `test_platform_reports_m1f0.py` (new)
- `test_report_output_m1f0.py` (new)
- `test_org_report_aggregation.py`
- `test_org_report_api.py`
- `test_org_report_registry_coverage.py`

Documentation and generated contracts:

- `docs/INVARIANTS.md`
- `docs/SOURCE-MAP.md`
- `docs/report-infrastructure.md` (this handoff)
- `frontend/openapi-schema.json`
- `frontend/src/generated/api.ts`
