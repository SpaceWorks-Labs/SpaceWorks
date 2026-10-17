# Phase 1f-2 booking and event builders

The D/E definitions are composed by `operations/report_definitions_de.py` and the existing
`booking-utilization` definition (version 2). Public columns live in `report_fields_de.py`.
No new model, endpoint, frontend, or generated snapshot is introduced.

All nine reports require their source module and its staff action: `bookings` /
`MANAGE_BOOKINGS`, or `events` / `MANAGE_EVENTS`. Top bookers additionally require
`VIEW_AUDIT` inside the builder, on both preview and export paths, and are omitted from
the catalog without that authority. These are resource booking reports, not machine
usage reports: an optional resource machine-type link adds no machine-management grant
or dependency. Machine type scope belongs to the separate machine report lane.

Every time axis supports day, ISO week (Monday), and month in the makerspace timezone.
Money uses `finance_sources`, including effective manual correction heads and successful
refunds. Deployment rows retain `makerspace_id`; they never flatten tenants.

| Key | Identity-bearing | Deployment aggregate | Schedulable | Chart hint | Organization |
| --- | --- | --- | --- | --- | --- |
| booking-utilization v2 | false | true | true | line | period totals; sum rate numerators/denominators |
| booking-occupancy | false | true | true | heatmap | excluded: local hour-of-week |
| booking-lead-time | false | true | true | histogram | excluded: timing distribution |
| booking-top-members | true | false | false | bar (10 + Other) | excluded: identities |
| event-signups | false | true | true | line | period totals; carry cumulative baselines |
| event-revenue | false | true | true | bar/time | period and currency sums |
| event-funnel | false | true | true | funnel | period totals; sum rate numerators/denominators |
| event-checkin-times | false | true | true | histogram | excluded: timing distribution |
| event-feedback-scores | false | true | true | bar | preserve event/question; sum scores and counts |

The F1 chart schema has no separate kind field: `chart_hint` supplies that type. Every
spec declares its dimensions, x axis, value units, currency partition, negative handling,
truncation and text alternative. Feedback preserves the question and event dimensions;
there is no cross-question score or assumption that different surveys share a scale.

## Fields and measurement boundaries

`makerspace_id` is additionally allowlisted for every deployment-capable report and is
present on every deployment row. Tenant rows omit it.

- **booking-utilization:** `period, space_id, space_name, kind, is_active, booked,
  completed, no_show, cancelled, upcoming, reserved_hours, completed_hours, window_hours,
  reservation_utilization_percent, no_show_rate_percent, cancellation_rate_percent,
  reservations, terminal_reservations`. Status counts are current outcomes bucketed by
  scheduled reservation start, not inferred transition timestamps. All statuses enter
  `reservations`; completed + no-show enter `terminal_reservations`. Elapsed reserved and
  completed hours are clipped and split across periods. Window hours require both bounds.
  The existing resource-subject reports retain their whole-window overlap contract.
- **booking-occupancy:** `period, weekday, hour, occupied_hours, window_hours,
  occupancy_percent`. This is reserved calendar occupancy, not physical presence.
  Confirmed/completed/no-show intervals are unioned per resource before counting;
  cancelled/pending/rejected intervals are excluded. Denominator is elapsed reporting
  time times the number of retained resources, including inactive resources (historical
  activation intervals are unavailable). No opening-hours calendar is inferred. An
  unbounded request observes the span of retained qualifying bookings. Empty cells in
  a bounded window are retained. DST repeats/gaps use real elapsed hours.
- **booking-lead-time:** `period, lead_time_bucket, booking_count`. Cohort is creation
  time; measure is creation to scheduled start in elapsed hours. Negative values have
  their own bucket. All reservation statuses count.
- **booking-top-members:** `member_id, member, booking_count, reserved_hours`. Confirmed,
  completed and no-show reservations with an actual member FK, selected by scheduled
  start. Unattributed legacy rows are omitted; contact fields are never used to guess an
  identity. Rank by count, tie by member ID; omitted ranked members contribute to Other.
- **event-signups:** `event_id, title, period, registrations, cumulative_registrations`.
  Counts every registration creation regardless of its later status. Cumulative values
  include the pre-window baseline and remain flat through idle buckets.
- **event-revenue:** `event_id, title, period, currency, charge_count, charged_amount,
  promo_discount_amount, collected_amount, refunded_amount, outstanding_amount, net_amount`.
  Host-owned ledger -> registration -> event join, never collaborator provenance. Charge
  and discount use charge creation; collections/refunds use the canonical finance dates.
  Discounts count once per linked charge, not once per settlement. Fully discounted/free
  registrations without a charge have no frozen ledger currency and are omitted.
  Outstanding means currently pending debt allocated to creation, not a historic balance.
  All amounts are major currency units. The optional payments rail is not a prerequisite.
- **event-funnel:** `event_id, title, period, registrations, confirmed, attended,
  confirmation_rate_percent, attendance_rate_percent`. Registration-creation cohorts;
  current registered + attended count as confirmed, current attended count as attended.
  These are current cohort outcomes, not reconstructed historical transitions.
- **event-checkin-times:** `event_id, title, period, timing_bucket, checkin_count`.
  First non-legacy `attended_at` per registration, selected before date filtering, against
  the event start. Reentry and delayed offline receipt do not duplicate arrivals. Legacy
  migration evidence has no reliable arrival timestamp and is excluded.
- **event-feedback-scores:** `event_id, title, period, question_id, score_count,
  score_total, average_score`. Feedback-creation cohorts; only finite numeric answers
  from the decrypted canonical snapshot. Text, labels and raw snapshots never leave the
  builder. Each question stays separate; organization averages divide summed totals by
  summed counts within the same event/question/period.

## Verification handoff

Tests are in `backend/tests/analytics/test_de_*_m1f2.py`, with shared fixtures in
`de_helpers_m1f2.py`. They cover tenant/aggregate scope, module and action fences, grains,
DST, weighted organization rates, currency partitioning, check-in deduplication,
cumulative baselines, numeric-only feedback, top-N and disclosure-safe JSON/CSV/XLSX.
The eight new keys are removed from the infrastructure coverage contract's strict xfails.
The three older booking report tests have been adjusted for the versioned time-series
schema and the separation between scheduled-start outcomes and subject overlap counts.

Claude owns test execution and review gates for this builder lane. Run the new test files,
the four 1f-0 contract files, and the existing operations reports tests with the isolated
runner before integration. Nothing is staged or committed by the implementer.

## Changed files

Under `backend/apps/operations/` (21 files):

- `org_report_de.py` (new)
- `org_report_scope.py`
- `org_report_strategies.py`
- `report_condition_metrics.py`
- `report_coverage.py`
- `report_definitions_bookings.py`
- `report_definitions_de.py` (new)
- `report_definitions_existing.py`
- `report_fields_de.py` (new)
- `report_registry.py`
- `reports.py`
- `reports_bookings.py`
- `reports_booking_analytics.py` (new)
- `reports_booking_trends.py` (new)
- `reports_de_common.py` (new)
- `reports_event_analytics.py` (new)
- `reports_event_quality.py` (new)
- `reports_event_revenue.py` (new)
- `schemas_reports.py`
- `serializers_reports_de.py` (new)
- `views_reports.py`

Tests (8 files; these paths are ignored by the repository's existing ignore rules):

- `backend/tests/analytics/de_helpers_m1f2.py` (new)
- `backend/tests/analytics/test_de_bookings_m1f2.py` (new)
- `backend/tests/analytics/test_de_contract_m1f2.py` (new)
- `backend/tests/analytics/test_de_events_m1f2.py` (new)
- `backend/tests/operations/test_grain_and_coverage_m1f0.py`
- `backend/tests/operations/test_booking_resource_reports.py`
- `backend/tests/operations/test_report_exports_fablab.py`
- `backend/tests/operations/test_reports_fablab.py`

Documentation (2 files): `docs/SOURCE-MAP.md`, `docs/report-builders-de.md` (new).
