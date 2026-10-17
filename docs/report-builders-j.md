# Analytics 1f-2 area J / 1f-3 builder handoff

Implemented in lane/mobile-1f2-j. Tests and reviews are left to the orchestrator;
no tests, Codex CLI, review gates, staging, commits or snapshot generation were run.
Python AST parsing and `git diff --check` were used for static verification.

## Reports and privacy

All time-series keys support day, ISO Monday week and month. Tenant calendars use
the makerspace timezone; platform and global organization cohorts use UTC. The
hour-of-week variants have categorical axes, not calendar grains. Every key has a
validated F1 chart specification, explicit units and an output allowlist.
Calendar filters are rebound at the builder boundary so preview, export, organization
and scheduler callers use the same dates; rolling windows retain their instants.

| Key | Identity-bearing | Deployment aggregate | Schedulable | Chart kind | Organization |
| --- | --- | --- | --- | --- | --- |
| device-health | false | true | true | stacked_bar | weighted rates from online/known seconds and acknowledged/terminal commands; group period/device |
| presence-activity | false | true | true | line | sum visits/seconds; union private visitor sets; divide seconds by summed visits |
| presence-top-visitors | true | false | false | bar, top 10/Other | excluded |
| presence-activity-hours | false | false | false | heatmap | excluded: local time-of-day |
| audit-activity | false | true | true | line, top 10 actions/Other | sum period/action counts |
| audit-top-actors | true | false | false | bar, top 10/Other | excluded |
| audit-activity-hours | false | false | false | heatmap | excluded: local time-of-day |
| organization-membership | false | true | false | funnel | deduplicate owner projections by organization/UTC cohort; recompute redeemed/invitations |
| module-operational-health v2 | false | true | true | table | existing exclusion: per-tenant configuration/custody health |
| platform-services | false | true | false | stacked_bar | platform-only; excluded |
| platform-usage | false | true | false | line, top 10/Other | platform-only; excluded |

Counts-only is represented by `identity_bearing=False`. All deployment-capable
definitions declare `makerspace_id`; tenant builders omit that infrastructure
column. Platform global facts carry a NULL makerspace. The sole anonymous tenant
exception is the hidden service/day bucket in platform-services, produced through
the infrastructure helper. It contains service/day/bucket/count only; other
columns are absent internally and NULL in the public matrix projection.

## Exact public fields

`makerspace_id` is additionally declared for every deployment-capable key below.

- **device-health:** period, device_id, online_seconds, offline_seconds,
  unknown_seconds, uptime_percent, offline_incidents, commands,
  commands_acknowledged, commands_failed, command_success_percent, label_prints,
  labels_printed, label_failures.
- **presence-activity:** period, visits, unique_visitors,
  declared_presence_seconds, average_declared_presence_seconds.
- **presence-top-visitors** and **audit-top-actors:** person_id, count,
  declared_presence_seconds. The duration is NULL for audit actors.
- **presence-activity-hours** and **audit-activity-hours:** weekday, hour, count,
  declared_presence_seconds. Audit duration is zero; presence count is the number
  of session/hour contributions, and declared seconds is its occupancy measure.
- **audit-activity:** period, action, count.
- **organization-membership:** period, organization_id, invitations, redeemed,
  revoked, expired, open_invitations, memberships, active_memberships,
  suspended_memberships, redemption_percent.
- **module-operational-health v2:** module_key, enabled, runtime_available,
  coverage_kind, activity_count, failure_count, last_activity_at,
  rollup_watermark, rollup_state, period, delivery_kind, delivery_count,
  success_count, success_rate_percent.
- **platform-services:** makerspace_id, period, day, service, provider_source,
  status, bucket, count, currency, amount.
- **platform-usage:** makerspace_id, period, metric, entity_kind, entity_id,
  unit, currency, value.

## Measurement and authority decisions

- Device uptime begins as unknown and changes only on retained enrollment/offline/recovery
  events. A pre-window event seeds the opening state. The uptime denominator
  excludes unknown seconds; the command-success denominator excludes queued,
  leased and cancelled commands. Status durations split at local calendar
  boundaries using elapsed instants, including DST. Label success uses terminal
  label commands and their item-count snapshots, gated on qr_print_batches.
- Presence durations are declarations, capped at observation time and explicit
  expiry/ending. Visit cohorts use session start time. The separate occupancy
  heatmap clips overlapping sessions to the requested window and splits elapsed
  seconds by local hour. Visitor IDs are private organization combine inputs and
  are removed by the public projection. Presence needs MANAGE_MEMBERS; visitor
  rankings additionally check VIEW_AUDIT. Audit rankings need VIEW_AUDIT.
- Audit action dimensions come from the presentation catalog. Unknown text becomes
  unrecognized; known credential-operation names use neutral credential labels.
  Raw audit metadata, actor names and free-text action input never enter counts.
- Organization membership is ORG + PLAT only: tenant catalog, preview, export and
  picker access refuse it; it cannot be scheduled. The existing organization
  membership/action/OWNER resolver remains its authority. Each owner-linked
  breakdown repeats the same global organization cohort, and combination counts
  that cohort once. An authorized organization can see its own global funnel even
  before it owns a makerspace; that global total has an empty tenant breakdown.
  Platform enumeration uses PlatformContext and includes unlinked organizations as
  deployment-attributed rows, excluding organizations linked solely to hidden spaces.
  Invitation outcomes and membership status are current states
  of creation cohorts, not historical state-change events.
- Delivery health retains every original module summary and adds dated report
  deliveries, tenant archives and offsite uploads. Rates use terminal outcomes.
  No report object keys, destinations, errors or backup locators are exposed.
- Platform builders require a server-minted active-superadmin PlatformContext even
  on direct calls. Services use recorded provider_source, both per-device push
  ledgers, SMS/attestation ledgers and backup coverage/standalone runs. Parent push
  deliveries and retry counters are not counted again. Hidden own-provider usage
  is excluded; hidden platform usage has no outcome or currency breakdown.
- Connect is limited to attributed charges, effective settlements and succeeded
  refunds through finance_sources. Amounts stay per currency; no provider-attempt
  failure series is inferred. Own-provider payment usage is counts only. Backup
  runs with tenant coverage are counted through that coverage, without a second
  deployment run row that could expose hidden outcomes or duplicate operations.
- Platform usage retains makerspace rows for loans, borrowed products, bookings,
  events, revenue/refunds per currency, machine hours, consumables, growth and
  adoption. Service, manual and booked hours remain separate. Machine reads use
  manage_scope_for and type predicates. Consumables use M1 v3 finalized service
  quantities, manual-use adjustments and non-pool debits once; recorded costs use
  ConsumableCostRecord only. Missing costs remain unknown, not zero.
- App sessions deduplicate DeviceActivityDay grants across visible tenants and NULL
  attribution per recorded local day. A daily count is assigned to its first
  visible tenant, falling back to deployment-only attribution; weekly/monthly
  sums are active session-days. Global app registrations have deployment attribution.
  Hidden and archived tenant business rows never enter platform usage.
- Platform-services partitions money charts by currency and includes makerspace
  in series. Platform-usage partitions by unit, keeps currency and makerspace in
  series, and never adds the three machine-hour measures together. Hidden service
  counts retain their daily calendar even when visible trends use week/month.
- Prometheus gains a platform/status push-outcome gauge from both ledgers. A gauge
  describes retained current outcomes accurately; retries can change row status.

## Endpoints

- GET `/api/v1/admin/platform/analytics/platform-services`
- GET `/api/v1/admin/platform/analytics/platform-usage`
- GET `/api/v1/admin/platform/analytics/makerspaces`

The first two accept start/end, grain and limit. The picker is DRF-paginated at 24
rows and accepts a tenant report_key. Hidden spaces require an explicit active
local membership granting that report's action. Platform metrics always retain
the stricter exclusion, regardless of local membership. Every new route has an
extend_schema request/response/error declaration; snapshots were left untouched.

## Files changed

New under `backend/apps/operations/`:

- metrics_push.py
- org_reports_j.py
- report_definitions_j.py
- report_fields_j.py
- reports_j_activity.py
- reports_j_common.py
- reports_j_devices.py
- reports_j_health.py
- reports_j_organizations.py
- reports_platform_consumables.py
- reports_platform_services.py
- reports_platform_usage.py
- views_platform_analytics.py

Updated under `backend/apps/operations/`:

- org_report_scope.py
- org_report_strategies.py
- report_condition_metrics.py
- report_coverage.py
- report_registry.py
- reports.py
- urls.py
- views_metrics.py
- views_report_helpers.py
- views_reports.py
- views_org_reports.py

Tests written (repository-ignored; include them explicitly in the integration):

- backend/tests/analytics/test_j_activity_m1f2.py
- backend/tests/analytics/test_j_contract_m1f2.py
- backend/tests/analytics/test_j_devices_m1f2.py
- backend/tests/analytics/test_j_exports_m1f2.py
- backend/tests/analytics/test_j_measurements_m1f2.py
- backend/tests/analytics/test_j_organizations_health_m1f2.py
- backend/tests/analytics/test_j_platform_m1f2.py
- backend/tests/operations/test_grain_and_coverage_m1f0.py (completed keys unmarked)

Documentation: docs/SOURCE-MAP.md and docs/report-builders-j.md.

## Orchestrator verification

Run the seven `test_j_*_m1f2.py` files together with the existing operations
registration/coverage/privacy/org-combination tests in the isolated test runner.
The credential/PII helper is called on projected responses across the new keys.
No runtime validation claim is made by this lane: Django/pytest are absent on the
host, and the orchestrator owns test execution by explicit instruction.
