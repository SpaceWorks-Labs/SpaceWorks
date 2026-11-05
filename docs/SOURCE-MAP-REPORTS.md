# Source map: reports and measurement notes

Continued from [SOURCE-MAP.md](SOURCE-MAP.md). This page says where each report family lives and what
its numbers mean: what is counted, what is left out, which rows carry identities and how organization
totals are combined. Paths are relative to `backend/apps/` unless they say otherwise. If this page
disagrees with the code, the code wins; fix this page in the same commit.

## Report infrastructure

### Registry, output allowlist and privacy

- `operations/report_registry.py` composes `REPORT_DEFINITIONS` from one tuple per area in
  `operations/report_definitions_<area>.py`. To change an existing key, extend its existing definition.
- `operations/report_types.py` owns `ReportDefinition`: `fields`, source-module gates, staff action,
  `grains`, `version`, `chart_hint`, `chart_spec`, and the flags `schedulable`, `deployment_aggregate`,
  `platform_only` and `identity_bearing`. `operations/report_validation.py` checks them on lookup and
  through the `operations.E005` system check.
- Every public field is declared, summary fields included. Deployment-capable definitions also declare
  `makerspace_id`; tenant builders may omit it.
- `operations/report_output.py` is the one output allowlist for previews, downloads and scheduled
  artifacts. An undeclared field is dropped with a structured warning. Builder metadata has its own
  scalar allowlist, `report_output.META_FIELDS`; declare new measurement or provenance metadata there.
- `identity_bearing=True` requires `deployment_aggregate=False`, `schedulable=False` and an entry in
  `org_report_scope.EXCLUDED_ORGANIZATION_REPORT_KEYS`. `platform_only=True` requires
  `deployment_aggregate=True` and `schedulable=False`.
- `top-borrowers`, `active-loans` and `returns` are identity-bearing, tenant-only and unschedulable.
  `active-loans` and `returns` (v2) carry `count=1` per detail row, so counts cover only returned rows.
- Aggregate output never carries raw audit metadata, payloads, message bodies or feedback answers.
  Only an intentional tenant-local subject export may include subject rows.

### Platform builders and organization combination

- A platform builder takes `platform_context` and calls
  `platform_scope.require_platform_context(platform_context)` before reading data, even when called
  directly. Only superadmin aggregate and platform views mint the context, through the private view
  factory in `operations/platform_scope.py`. `platform_analytics_spaces(ctx)` enumerates spaces via
  `platform_dashboard.platform_spaces()`. Tenant-local views authorize with the report's own action.
- For organization views, declare the key in `org_report_strategies.STRATEGIES` and call
  `org_report_aggregate.register_combine(report_key, combine)` from the area's definitions module.
  `combine(rows_by_space, *, limit)` gets `(makerspace_id, records)` pairs with every private field and
  returns a list of dictionaries. Orchestration runs in `org_reports.py` and `views_org_reports.py`.
- Sum numerators and denominators before dividing. Keep period, currency and unit partitions. Private
  denominator fields are removed only at the final public projection.
- Medians, percentiles, time-of-day heatmaps and identity rankings are excluded from organization views.

### Grains, coverage and conditions

- A builder that supports weeks lists `week` in `definition.grains`; ISO weeks start on Monday.
  `reports_common.period_expression(field, grain, makerspace=space)` gives a tenant-local SQL bucket
  (`tzinfo=zone` for a resolved zone). Organization views forward the grain only to grain-aware builders.
- `operations/report_coverage.py` holds `REPORT_MODULE_COVERAGE`; the acceptance table is
  `report_coverage_contract.REPORT_COVERAGE_CONTRACT`. A coverage association is not a runtime
  dependency. `presence`, `audit`, `organizations` and `platform` are coverage-only, not module gates.
  `evidence-compliance` maps only to `evidence_uploads`, `import-quality` only to `bulk_import`.
- Numeric threshold columns for schedule conditions live in `report_condition_metrics.NUMERIC_FIELDS`.

### Chart specification

Every previewable definition needs a valid `chart_spec`. `report_validation.validate_chart_spec`
enforces it, `operations/serializers_report_chart.py` owns its OpenAPI shape, and catalogs return
`chart_spec` and `identity_bearing`.

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

- All keys are required and every referenced field must be in the output allowlist. `x.kind` is `time`
  or `category`; `partition` is `tenant`, `currency`, `unit` or null; `negatives` is `allow` or `clip`;
  `truncation` is null or a positive `top_n` with a non-empty `other_label`.
- Currency partitioning needs `currency_field`; tenant partitioning needs `makerspace_id`.
  `alt_template` placeholders are plain declared fields or `count`, with no expressions.
- A value may add `kind=line|stacked_bar`. Only mutually exclusive outcomes stack; cumulative counts,
  overlays and ratios stay lines.
- There is no `{"kind": "table"}` shortcut. A table spec has a category row dimension, empty `values`
  and no aggregation, so the client never sums IDs.
- `operations/report_charts_remaining.py` holds the specs for older keys. Ledger and journal charts
  partition by currency, use major units and keep negative values. The audit trail has a spec but stays
  CSV-only.
- `most-lent` v2 keeps undated legacy loans as a null period in unbounded reports; dated windows exclude
  them. `fablab-health` v2 includes `makerspace_id` in local rows too.

## Bookings and events (areas D and E)

Files under `operations/`: `report_definitions_de.py`, `report_fields_de.py` (public columns),
`org_report_de.py`, `reports_de_common.py`, `reports_booking_analytics.py`, `reports_booking_trends.py`,
`reports_bookings.py`, `reports_event_analytics.py`, `reports_event_quality.py`,
`reports_event_revenue.py`, `serializers_reports_de.py`. `booking-utilization` is defined in
`report_definitions_existing.py`.

- Each report needs its module and action: `bookings` with `MANAGE_BOOKINGS`, or `events` with
  `MANAGE_EVENTS`. `booking-top-members` also checks `VIEW_AUDIT` in the builder, and the catalog hides
  it without that action. A resource's machine-type link grants no machine authority.
- Day, ISO week and month in the makerspace timezone. Money comes from
  `reports_finance_sources.finance_sources`, including manual corrections and successful refunds.
  Deployment rows keep `makerspace_id`.

| Key | Identity-bearing | Deployment | Schedulable | Chart | Organization |
| --- | --- | --- | --- | --- | --- |
| booking-utilization v2 | no | yes | yes | line | period totals; summed rate parts |
| booking-occupancy | no | yes | yes | heatmap | excluded (local hour of week) |
| booking-lead-time | no | yes | yes | histogram | excluded (timing distribution) |
| booking-top-members | yes | no | no | bar, top 10 + Other | excluded (identities) |
| event-signups | no | yes | yes | line | period totals; cumulative baselines carried |
| event-revenue | no | yes | yes | bar over time | sums by period and currency |
| event-funnel | no | yes | yes | funnel | period totals; summed rate parts |
| event-checkin-times | no | yes | yes | histogram | excluded (timing distribution) |
| event-feedback-scores | no | yes | yes | bar | per event and question; summed scores and counts |

- **booking-utilization:** current outcomes bucketed by scheduled start, not reconstructed transitions.
  All statuses count in `reservations`; completed and no-show in `terminal_reservations`. Hours are
  clipped and split across periods; window hours need both bounds.
- **booking-occupancy:** reserved calendar time, not physical presence. Confirmed, completed and no-show
  intervals are unioned per resource. The denominator is elapsed time times retained resources, inactive
  ones included. No opening hours are inferred. DST uses real elapsed hours.
- **booking-lead-time:** creation to scheduled start in elapsed hours, cohorted by creation. Negative
  values get their own bucket.
- **booking-top-members:** confirmed, completed and no-show reservations with a real member FK. Legacy
  rows without one are left out; contact fields are never used to guess an identity.
- **event-signups:** every registration creation, whatever its later status. Cumulative values include
  the pre-window baseline.
- **event-revenue:** host ledger to registration to event, never collaborator provenance. Charges and
  discounts date from charge creation; collections and refunds use finance dates. A discount counts once
  per charge. Free registrations have no currency and are omitted. Outstanding is current pending debt.
  Major currency units; the payments rail is not required.
- **event-funnel:** registration cohorts with current outcomes, not historical transitions.
- **event-checkin-times:** the first non-legacy `attended_at` per registration against event start.
  Re-entry and late offline receipt add nothing. Legacy migration evidence is excluded.
- **event-feedback-scores:** finite numeric answers only. Text and raw snapshots never leave the
  builder. Questions are never merged across surveys.

## Areas H and I

Files under `operations/`: `report_definitions_hi.py`, `report_fields_hi.py` (public allowlists),
`reports_hi_common.py`, `reports_communications.py`, `reports_mobile_devices.py`,
`reports_mobile_auth.py`, `reports_mobile_platform.py`.

All three keys are counts-only, deployment-capable and schedulable, with tenant-local day, week and
month. Rows never contain destinations, person IDs, message bodies, raw metadata, provider errors or
credentials. Audit dimensions and reasons use closed vocabularies.

- `communications-health` v4: see [Communications and messaging](#communications-and-messaging).
- `mobile-devices` v2: period, metric, platform, environment, authority, status, count. Line chart.
- `mobile-auth` v2: period, metric, platform, environment, outcome, reason, count. Stacked bar.
- Both mobile keys require `mobile` and combine across organizations as a sum by every dimension.

Mobile measurement boundaries:

- Push devices and grants are current snapshots (`period=null`). Registration and invalidation trends
  use recorded dates and retained rows only; they are not a full device history.
- A grant belongs to a tenant only through a tenant-scoped registration or a recorded activity row.
  Membership alone is not attribution.
- `DeviceActivityDay` is the activity source. A day counts distinct grants; week and month sum
  session-days. Organization sums can count a shared grant once per tenant.
- Mobile authentication reads only audit rows with a recorded tenant or selected tenant. Some login
  writers do not record one, so those events are missing from tenant metrics. Attestation-caused login
  failures also appear in the attestation metric; do not add the two.
- `AttestationVerificationLog` has no tenant. Its counts are platform-only and never allocated.

## Area J

Files under `operations/`: `report_definitions_j.py`, `report_fields_j.py`, `org_reports_j.py`,
`reports_j_common.py`, `reports_j_activity.py`, `reports_j_devices.py`, `reports_j_health.py`,
`reports_j_organizations.py`, `reports_platform_services.py`, `reports_platform_usage.py`,
`reports_platform_consumables.py`, `views_platform_analytics.py`, `metrics_push.py` (Prometheus
push-outcome gauge).

Tenant calendars use the makerspace timezone; platform and global organization cohorts use UTC.
Calendar filters are rebound at the builder boundary so every caller sees the same dates.

| Key | Identity-bearing | Deployment | Schedulable | Chart | Organization |
| --- | --- | --- | --- | --- | --- |
| device-health | no | yes | yes | stacked_bar | weighted uptime and command-success rates |
| presence-activity | no | yes | yes | line | summed visits and seconds; union of private visitor sets |
| presence-top-visitors | yes | no | no | bar, top 10 + Other | excluded |
| presence-activity-hours | no | no | no | heatmap | excluded (local time of day) |
| audit-activity | no | yes | yes | line, top 10 actions + Other | summed period/action counts |
| audit-top-actors | yes | no | no | bar, top 10 + Other | excluded |
| audit-activity-hours | no | no | no | heatmap | excluded (local time of day) |
| organization-membership | no | yes | no | funnel | owner projections counted once per organization |
| module-operational-health v3 | no | yes | yes | table | excluded (per-tenant health) |
| platform-services v3 | no | yes | no | stacked_bar | platform-only |
| platform-usage | no | yes | no | line, top 10 + Other | platform-only |

Global platform facts carry a NULL makerspace. There is no anonymous tenant bucket. Hidden and archived
tenants never enter platform usage.

- **device-health:** uptime starts unknown and changes only on retained enrollment, offline and recovery
  events. Unknown seconds are excluded from uptime. Command success excludes queued, leased and
  cancelled commands. Label success is gated on `qr_print_batches`.
- **presence:** durations are declarations, capped at observation time and expiry. Visits are cohorted
  by session start. Visitor IDs are private combine inputs. Needs `MANAGE_MEMBERS`; rankings of visitors
  or audit actors also need `VIEW_AUDIT`.
- **audit:** action names come from the presentation catalog; unknown text becomes unrecognized and
  credential operations get neutral labels. Raw metadata, actor names and free text are never counted.
- **organization-membership:** organization and platform scope only; tenant catalog, preview, export
  and picker refuse it. Invitation and membership states are current states of creation cohorts.
- **module-operational-health:** adds report deliveries, tenant archives and offsite uploads to every
  module summary. No object keys, destinations, errors or backup locators are exposed.
- **platform-services:** uses recorded `provider_source`, both per-device push ledgers, SMS and
  attestation ledgers, and backup coverage. Parent push deliveries and retries are not counted again.
  Connect counts attributed charges, effective settlements and succeeded refunds per currency.
- **platform-usage:** loans, bookings, events, money per currency, machine hours, consumables, growth
  and adoption. Service, manual and booked hours are never added together. Machine reads go through
  `manage_scope_for`. Costs come only from `ConsumableCostRecord`; a missing cost stays unknown, not zero.

Platform routes: `GET /api/v1/admin/platform/analytics/platform-services`, `.../platform-usage` and
`.../makerspaces` (a paginated picker of every servable space).

## Machines

Files under `operations/`: `report_definitions_machines.py`, `reports_machine_common.py`,
`reports_machine_facts.py`, `reports_machine_usage_v2.py`, `reports_machine_heatmap.py`,
`reports_machine_downtime.py`, `reports_machine_maintenance_v2.py`, `reports_machine_service_v2.py`,
`reports_machine_queue.py`, `reports_machine_health.py`, `org_machine_reports.py`,
`org_machine_report_schemas.py`, `serializers_reports_machine_analytics.py`.

- Every key uses `MANAGE_MACHINES`, resolved through `manage_scope_for()` (`machines/role_scope.py`).
  Preview, export, schedules and organization runs all forward the actor, so an organization grant
  never bypasses machine-type scope. `machine-usage-members` also needs `VIEW_AUDIT` and emits member IDs
  only; null is the unattributed bucket.
- Day, week and month use tenant-local SQL buckets. No chart adds different hour measures, units or
  currencies.

| Key | Version | Identity-bearing | Deployment | Schedulable | Chart | Organization |
| --- | --- | --- | --- | --- | --- | --- |
| machine-usage | 2 | no | yes | yes | multi_line | sums by period, measure, machine and type |
| machine-usage-members | 1 | yes | no | no | bar | excluded (identities) |
| machine-usage-heatmap | 1 | no | yes | yes | heatmap | excluded (time of day) |
| machine-downtime | 1 | no | yes | yes | stacked_bar | sums by period, machine and status |
| maintenance-activity | 2 | no | yes | yes | line | per period and machine; weighted averages |
| machine-service | 2 | no | yes | yes | line | weighted failure rate |
| service-queue-times | 1 | no | yes | yes | line | excluded (medians and percentiles) |
| printer-jobs | 1 | no | yes | yes | stacked_bar | sums by period, machine, state and outcome |
| machine-errors | 1 | no | yes | yes | stacked_bar | sums by period, machine and severity |
| warranty-expiry | 1 | no | yes | yes | table | union by warranty ID |

- **Hours:** service hours read the terminal request's `actual_minutes`, failed partial work included,
  bucketed at completion or failure. Manual hours bucket at `started_at`, booked hours at reservation
  start (confirmed, completed and no-show only).
- **Usage preview** keeps five machines or types per measure plus Other. Exports and organization
  source builds keep every machine, so combination happens before ranking.
- **Heatmap** splits real intervals at local hour boundaries, DST included. Manual entries without
  `started_at` are omitted; incomplete service intervals are not extrapolated.
- **Downtime** reads only `MachineStatusEvent`. The last event at or before the start sets the opening
  state; earlier time is unknown.
- **Maintenance** buckets by `performed_at`. Logs have no recorded currency, so amounts are labelled
  unknown, stay per machine and are never charted or totalled as money.
- **Machine service:** `failure_rate` is failed over completed plus failed, recomputed after summing.
- **Queue times:** stages run created, accepted, started, completed, collected. Only observed
  non-negative durations count; percentiles use linear interpolation.
- **Printer jobs** show current state by creation period; jobs on deleted machines are omitted.
  **Machine errors** count severity only and never select diagnostic text.
- **Warranty** output leaves out vendor contacts and documents. Days until expiry use the local date.

## Communications and messaging

`communications-health` v4 is built by `operations/reports_communications.py`. Canonical facts come
from `integrations/reports_messaging.py` and, under `operations/`, `reports_notification_facts.py`,
`reports_notification_receipts.py`, `reports_notification_consent.py`, `reports_push_facts.py` and
`reports_communications_ledgers.py`. Organization combination is in `org_reports_messaging.py`.
Delivery itself is mapped in [SOURCE-MAP-NOTIFICATIONS.md](SOURCE-MAP-NOTIFICATIONS.md).

- Each section needs its real module: `email`, each chat channel, `notifications` for the inbox,
  `mobile` for staff push. SMS, WhatsApp and canonical push do not need the inbox.
- Reports are read-only. They never replay callbacks, enable sending or dispatch queues.
- The retired `MessagingDelivery` table is never read. `NotificationLegacyMapping` rows add original
  history after tenant and target validation; they are not extra deliveries.
- Push uses `PushDeliveryAttempt` and `MemberPushDelivery`, never the parent's outcome. Retries add
  attempts, not sent messages.
- Email bounces and complaints use their own timestamps and can overlap sent counts, so they are drawn
  as lines. Inbox read rate is read over created (`NotificationInboxRow`) for the creation cohort.
- Cohorts use `NotificationDelivery.created_at`, bucketed by tenant-local day, ISO week or month.
  Outcomes are current, not reconstructed as of the window end. Retention limits history.
- No phone, sender key, provider ID, body, template name, provider text or credential enters a row.
- Cumulative accepted, sent, delivered and read counts include later progress. Exclusive outcomes are
  pending, sending, accepted_only, sent_only, delivered_only, read, failed, skipped, suppressed, held.
- `delivery_rate` is delivered over accepted; `read_rate` is read over delivered. A zero denominator
  gives null, and each rate exposes its numerator and denominator.
- SMS `segments` prefers the billed count, including zero, else the estimate; `segment_source` says
  which. Estimates on skipped rows are not charges. WhatsApp segments are `not_applicable`.
- `held_webhook_count` counts held `NotificationIngress` by original received date.
  `abandoned_webhook_count` counts original abandoned legacy receipts. Unattributed receipts are never
  assigned to a guessed tenant.
- `consented_member_count` is a current snapshot (`period=null`) of active, unrestricted members with
  current SMS or WhatsApp proof. Staff sharing a contact are not counted. Organization totals leave it
  out; it stays in tenant breakdowns. SMS OTP volume is in `platform-services` (`SmsSendLog`).

Routes: `GET /api/v1/admin/makerspace/{id}/analytics/communications-health` and
`.../reports/communications-health/export` (tenant), `GET /api/v1/admin/analytics/communications-health`
(deployment) and `GET /api/v1/admin/organizations/{id}/analytics/communications-health` (organization).
Sending activation depends on the [replay sign-off checkpoints](notification-reconciliation-rollout.md).
