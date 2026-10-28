# Canonical communications and messaging measurements

`communications-health` version 4 is registered to
`operations.reports_communications.build_communications_health`. It composes canonical personal
chat and SMS/WhatsApp delivery facts with retained room logs, physical email outcomes from EmailLog,
per-device push ledgers and optional inbox reads. Each section uses its real module. SMS/WhatsApp
and canonical push do not require inbox installation; push adapter registration still belongs to
the notifications app. All reads are tenant-scoped. Deployment rows retain makerspace_id.
Reports are read-only: they never replay callbacks, activate sending or dispatch queues.

## Sources and cohorts

`integrations.reports_messaging`, `operations.reports_notification_facts`,
`reports_notification_receipts`, `reports_notification_consent` and `reports_push_facts` project
canonical data. The retired MessagingDelivery table is never queried by production reporting.
Unique encrypted NotificationLegacyMapping records supplement original observations after exact
canonical-target and tenant validation. Mappings are history, not another delivery. Foundation
mappings preserve observations predating expanded timestamps. Push children supply outcomes once;
their parent is not counted again. Parent tenant/audience attribution works without an inbox row.

Creation cohorts use canonical NotificationDelivery.created_at (device rows use their ledger's
creation time), bucketed by tenant-local day, ISO Monday week or month. Calendar labels resolve
in each tenant before filtering, including DST; precise windows retain instants. Current recorded
outcomes are not historical as-of-window-end reconstructions. Retention limits available history.
Groups retain period, module/channel, feature, audience including requester, own/platform source,
platform, closed-vocabulary skip reason, segment source and measurement. Unknown categories map
to unknown. No phone, sender key, provider ID, body/context, template name, provider text or
credential enters report rows. Failures do not erase delivered/read observations.

## Counts, rates and provenance

- Cumulative accepted/sent/delivered/read counts derive from the canonical progress observations
  plus mapped original history. accepted_count includes later sent/delivered/read; sent_count
  includes later delivery failure. read_count is the highest observed progress.
- Current failed_count reflects the derived current failure, not merely failed_at. Exclusive
  outcomes distinguish pending, sending, accepted_only, sent_only, delivered_only, read, failed,
  skipped, suppressed and held. Canceled legacy queues retain their disposition in immutable
  mappings and inert canonical history; cancellation never schedules work.
- delivery_rate = delivered / accepted; read_rate = read / delivered. Zero denominators return
  null. Each rate exposes numerator/denominator; existing percent fields remain percentages.
  Inbox read percentage retains its separate read/created meaning.
- SMS estimated_segments and billed_segments are separate. segments prefers a recorded bill,
  **including zero**, otherwise the estimate; segment_source labels billed/estimated. Retained
  estimates on skipped rows are observations, not incurred financial charges. WhatsApp is
  not_applicable for segments.
- held_webhook_count measures current held NotificationIngress by original received_at cohort,
  with measurement=webhook_receipts. abandoned_webhook_count measures original abandoned legacy
  receipt snapshots with their original dates. Those observations do not assert a replayed
  receipt remains abandoned. Unattributed platform receipts cannot be assigned to a guessed
  tenant; rejected signatures have no fabricated zero-valued metric.
- consented_member_count is a current, date-filter-independent member-account snapshot with
  measurement=current_consent_snapshot and period=null. It excludes restricted/inactive/deleting
  members. SMS compares current phone verification instance, sender and generation; WhatsApp
  requires current signed endpoint proof and no opt-out. Staff sharing the contact never enter
  the member count. Account-only recipients enter delivery cohorts even though this specifically
  named member snapshot does not count them.

Public numeric allowlists/condition metrics include held_count and held_webhook_count.
Previews, exports, dashboards and typed responses use the same sanitized projection.

## Organizations, charts and platform metering

Organization combination preserves dimensions, sums additive observations and recomputes weighted
rates from summed numerators/denominators. Current consent snapshots remain in tenant breakdowns
and are excluded from combined totals. Keep the combined total beside every tenant breakdown.
Only exclusive outcomes may be stacked; cumulative progress, overlays and ratios remain lines.
Chart specifications preserve units, tenant and currency partitions and full table fallback.

`platform-services` and `module-operational-health` are version 3; `mobile-devices` and
`mobile-auth` are version 2. SMS OTP comes from SmsSendLog, independently of canonical notification
SMS/WhatsApp. Logical notifications count once despite retries. Own/platform source remains visible
for visible tenants; own-provider rows expose counts/outcomes without segment billing or amounts.
Pending debt never contributes to collected platform revenue; document/settlement accounting stays
on the canonical ledger. Historical usage is not erased by later module disablement.

A server-owned PlatformContext is required. Usage is grouped by makerspace for every servable space;
there is no anonymous hidden bucket.
Mobile reports recognize fixed-tenant native staff grants and current per-device children.

## HTTP and rollout

Use endpoint paths, with the regenerated OpenAPI response shapes:

- GET `/api/v1/admin/makerspace/{id}/analytics/communications-health` and its
  `/reports/communications-health/export` companion under the same tenant prefix.
- GET `/api/v1/admin/analytics/communications-health`, `/api/v1/admin/reports/catalog`,
  and `/api/v1/admin/reports/communications-health/export` for authorized deployment scope.
- GET `/api/v1/admin/platform/analytics/platform-services` for platform metering.
- GET `/api/v1/admin/organizations/{id}/analytics/communications-health` for breakdown/totals.
- GET `/api/v1/admin/makerspace/{id}/reports/catalog` and `/dashboard` for authorized catalog,
  condition fields, widgets and chart metadata. Machine scope and identity-bearing audit gates apply.

OpenAPI/TypeScript regeneration and runtime verification belong to the orchestrator after lanes
converge. Static/documentation checks establish no provider or migration success. Sending activation,
destructive integrations 0043 and callback compatibility remain subject to
[replay sign-off checkpoints](notification-reconciliation-rollout.md).
