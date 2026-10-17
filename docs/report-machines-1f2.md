# Phase 1f-2 area C: machine report builder handoff

Implemented on `lane/mobile-1f2-c`. Test execution, review gates and commits remain with
the orchestrator. No frontend, model, migration, tenant snapshot or OpenAPI snapshot edits.

Every key uses `MANAGE_MACHINES`, resolved through `manage_scope_for()` for an actor's
makerspace membership and assigned machine types. Preview/export dispatch and scheduled
exports forward the actor. Organization orchestration also forwards its actor; an
organization grant does not bypass local machine-type scope. The existing organization
administration restriction on granting machine authority is unchanged.

`machine-usage-members` additionally requires `VIEW_AUDIT`, including direct builder calls;
the catalog omits it without that action. It emits member IDs, never contact fields or
requester/staff attribution substituted for a member. Null is the unattributed bucket.

All time-series keys support **day/week/month**, using tenant-local SQL calendar buckets.
Weeks begin Monday. Tenant manual/scheduled date filters use the same local date bounds.
Organization filters retain the existing instant range contract; buckets are local per space.
Deployment reads batch spaces with the same timezone and optional source modules. Each
source fact retains its makerspace ID, and batched role-scope predicates AND each tenant
with its own type grants. Adding tenants to a cohort does not add source queries.

## Per-key contract

All counts-only deployment rows include `makerspace_id`. Tenant rows omit that field.
Chart kind below is `chart_hint`; `chart_spec` declares x, series, values/units, partition,
negative handling, truncation and alternative text. No chart adds different hour measures,
measurement units or currencies. Organization strategies retain period and machine/type/unit
partitions rather than flattening unlike measurements into a total.

| Key | Version | Identity-bearing | Deployment aggregate | Schedulable | Chart kind | Organization |
| --- | --- | --- | --- | --- | --- | --- |
| machine-usage | 2 | false | true | true | multi_line | group sums by period/measure/machine/type |
| machine-usage-members | 1 | true | false | false | bar | excluded: identities |
| machine-usage-heatmap | 1 | false | true | true | heatmap | excluded: time of day |
| machine-downtime | 1 | false | true | true | stacked_bar | group sums by period/machine/status |
| maintenance-activity | 2 | false | true | true | line | per-period/machine sums; weighted cost/interval averages |
| machine-service | 2 | false | true | true | line | per-period/kind/machine/measurement/product/outcome; weighted failure rate |
| service-queue-times | 1 | false | true | true | line | excluded: medians/percentiles |
| printer-jobs | 1 | false | true | true | stacked_bar | group sums by period/machine/state/outcome |
| machine-errors | 1 | false | true | true | stacked_bar | group sums by period/machine/severity |
| warranty-expiry | 1 | false | true | true | table | row union by unique warranty ID |

Public fields (plus `makerspace_id` in deployment definitions):

- **machine-usage:** period, measure, machine_id, machine_name, machine_type_id,
  machine_type, entries, service_hours, manual_hours, booked_hours.
- **machine-usage-members:** period, member_id, measure, machine_type_id, machine_type,
  entries, hours.
- **machine-usage-heatmap:** period, measure, machine_type_id, machine_type, weekday, hour,
  service_hours, manual_hours, booked_hours.
- **machine-downtime:** period, machine_id, machine_name, machine_type, status, status_hours.
- **maintenance-activity:** period, machine_id, machine_name, machine_type, is_active,
  log_count, costed_log_count, total_cost, average_cost, last_performed_at,
  average_interval_days, active_schedules, overdue_schedules, currency.
- **machine-service:** period, row_kind, submitted, accepted, in_progress, completed,
  collected, rejected, failed, machine_id, machine_name, machine_type, request_count,
  completed_count, failed_count, completed_hours, failed_partial_hours,
  total_recorded_service_hours, failure_rate, measurement, product_id, product_label,
  completed_amount, failed_partial_amount, total_used, outcome, failed_count_amount,
  failed_grams_amount.
- **service-queue-times:** period, queue_id, queue_name, bucket_id, stage, samples,
  median_minutes, p90_minutes, p95_minutes.
- **printer-jobs:** period, machine_id, machine_name, machine_type, state, outcome, job_count.
- **machine-errors:** period, machine_id, machine_name, machine_type, severity, error_count.
- **warranty-expiry:** warranty_id, machine_id, machine_name, machine_type, purchased_on,
  warranty_expires_on, days_until_expiry.

## Measurement details

- Service hours read terminal requests' **actual_minutes**, including failed partial work.
  The legacy report estimated failed hours from percentage of estimated duration; v2 uses
  recorded elapsed metering. Percent complete describes outcome, not elapsed time.
  Service hours bucket at completion/failure, manual ledger hours at started_at (creation
  for undated legacy entries), and booked hours at reservation start, by machine type.
  Confirmed/completed/no-show bookings count as reserved hours; cancelled/rejected/pending
  bookings do not. These three hour columns are separate schedule threshold metrics.
- Usage preview keeps five machines/types per measure over the complete selected window,
  plus Other rows partitioned by type. Unlimited exports and organization source builds
  retain all machines, allowing combination before ranking/limits. The chart declares
  top-five truncation explicitly.
- Heatmaps split real intervals at local hour boundaries, including repeated DST hours.
  Service interval hours come from started_at through completed_at/failed_at, so they can
  differ from recorded metering hours. Manual intervals need started_at; older undated
  entries are omitted. Incomplete service intervals are not extrapolated.
- Downtime reads only MachineStatusEvent. The last event at/before the range start supplies
  the initial state; earlier time is unknown, never inferred from current/from_status.
  Segments are clipped to the machine's existence and selected window, then split by grain.
- Maintenance buckets use performed_at. Current schedule counts have a null period and
  are not repeated in historic buckets. Logs have **no recorded currency**; legacy nominal
  amounts are labelled unknown and confined to each machine. They are not money chart
  values or cross-machine/tenant monetary totals. Interval averages retain private summed
  days/gap counts through organization calculation; output projection removes them.
- Service status rows show current statuses of submissions created in each bucket.
  Terminal counts/hours use their own terminal timestamp; failure_rate is percent failed
  over completed plus failed, recomputed after summed counts. Failure consumption columns
  are on machine rows, avoiding duplicated failed-count schedule thresholds. Consumption
  rows retain measurement/product partitions.
- Queue stages are created→accepted→started→completed→collected. Each stage buckets by
  its endpoint. Only observed nonnegative durations count. Median/p90/p95 use continuous
  linear interpolation; incomplete/failed stages do not invent samples.
- Printer jobs show the current tracked state/outcome by creation period, not reconstructed
  transition history. Jobs with deleted machines cannot be type-scoped and are omitted.
  Machine errors count severity only; diagnostic text is never selected.
- Warranty output is machine-only, has known expiry dates, filters by expiry, and omits
  vendor contact/documents. Days until expiry use the tenant's local current date.

## Changed files

New operations files:

`report_definitions_machines.py`, `reports_machine_common.py`, `reports_machine_facts.py`,
`reports_machine_usage_v2.py`, `reports_machine_heatmap.py`, `reports_machine_downtime.py`,
`reports_machine_maintenance_v2.py`, `reports_machine_service_v2.py`, `reports_machine_queue.py`,
`reports_machine_health.py`, `org_machine_reports.py`, `org_machine_report_schemas.py`,
`serializers_reports_machine_analytics.py`.

Updated operations files:

`report_registry.py`, `org_report_strategies.py`, `org_report_scope.py`, `org_reports.py`,
`views_org_reports.py`, `report_condition_metrics.py`, `report_coverage.py`, `reports.py`,
`views_reports.py`, `report_download.py`, `report_schedule_services.py`, `schemas_reports.py`.

Tests (the repository ignores backend/tests; retain these local files for integration):

`backend/tests/analytics/c_helpers_m1f2.py`, `test_c_contract_m1f2.py`,
`test_c_scope_m1f2.py`, `test_c_measurements_m1f2.py`, and
`backend/tests/operations/test_grain_and_coverage_m1f0.py` (ten completed keys removed
from strict xfail by an additive completion-set override).
Existing v1 expectations updated in `backend/tests/operations/test_reports_fablab.py`,
`test_report_exports_fablab.py`, `test_org_report_scope.py` and `test_org_report_api.py`.

Documentation: `docs/SOURCE-MAP.md` and this handoff.

Static Python parsing and whitespace checks pass. **No tests or review CLI were run**,
per the Stage 2 implementer instruction. The new tests cover schemas, grains, DST,
scope/action/module boundaries, top-five totals, organization math, and disclosure
guards on JSON and decoded CSV/XLSX. All touched production files remain below 300 lines.
