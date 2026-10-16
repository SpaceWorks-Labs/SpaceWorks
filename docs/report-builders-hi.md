# H/I report builder handoff (1f-2)

All three keys are counts-only (`identity_bearing=False`), deployment-capable and
schedulable. Every deployment row carries `makerspace_id`. The staff action is
`MANAGE_MAKERSPACE`; there are no machine sources or machine-type authority grants.
All time axes support tenant-local day, ISO week and month.

`report_fields_hi.py` owns the exact public allowlists. Deployment definitions add
`makerspace_id` through the registry. No output contains destinations, person IDs,
registration IDs, message bodies, raw metadata, provider errors or credentials.
Audit dimensions and reasons are projected through closed vocabularies.

- `communications-health` v2: period/module/channel/feature/provider source/platform;
  triggered, delivery, attempt, sent, failed, skipped, suppressed, bounced, complained,
  invalid, inbox-created, inbox-read and unread counts; success/read percentages;
  last activity time. Chart: multiple lines, time axis, explicit per-value units,
  tenant partition, no top-N truncation. Organization strategy: weighted rates,
  summed numerators/denominators, latest activity; dimensions stay separate.
- `mobile-devices`: period/metric/platform/environment/authority/status/count.
  Chart: line, metric-separated observations, tenant partition, no truncation.
  Organization strategy: group sum by every dimension. Requires `mobile`.
- `mobile-auth`: period/metric/platform/environment/outcome/reason/count.
  Chart: stacked bar, metric-separated event counts, tenant partition, no truncation.
  Organization strategy: group sum by every dimension. Requires `mobile`.

Communications sections independently require their real module: `email`, each
chat channel, `notifications` for personal inbox, and `mobile` for staff native
push. Member native push requires both `mobile` and `notifications`. Native push
uses `PushDeliveryAttempt` and its tracked member sibling `MemberPushDelivery`,
never the parent log's aggregate outcome or a device's later state. Retries add
attempts to one delivery, not extra sent messages. Invalid outcomes are disjoint
from other failures. Sent/delivery-cohort count is the success-rate definition.
Email bounce and complaint counts use their own timestamps and can overlap sent
counts; they are event overlays, not mutually exclusive delivery statuses.
The chart uses separate lines rather than adding these overlapping series into
a stacked total. Different value units remain labelled independently.

Inbox counts use `NotificationInboxRow`, not the legacy shared notification feed.
The read rate is read/created for the creation cohort, measured at the filter's
exclusive end (or current state without an end). It is not an independent read-event
trend. Organization combination preserves this denominator.

Push devices and grants are current snapshots (`period=null`), independent of the
event date filter. Push registration/invalidation trends use their recorded dates.
App registration rows are tenant-only here; global registrations are available only
through the platform-context source helper. Grants need either a tenant-scoped
registration or a recorded activity row for that tenant. Membership alone is not
attribution. Registrations and invalidations reflect retained rows; they are not an
append-only history of re-registrations or deleted devices.

`DeviceActivityDay` is the activity authority. A day counts distinct grants in the
recorded tenant; week/month sum daily session observations (session-days). Summed
organization observations count each tenant's sessions, so shared grants can occur
in several tenant partitions. The platform helper deduplicates grants across
visible tenant/NULL rows per recorded day and excludes hidden tenant rows.

Tenant mobile authentication reads only audit rows with a recorded tenant or
recorded selected tenant in metadata. It never follows actor memberships to infer
attribution. Legacy missing dimensions are `unknown`. Login failures explicitly
caused by attestation also appear in the attestation metric; these measures must
not be added together. The current login writers omit tenant/platform metadata on
several paths, so those events cannot contribute to tenant metrics until tracking
records that selection. This builder deliberately does not alter auth writers.

`AttestationVerificationLog` has no tenant/reason identifier. Its outcome/mode
counts are available through the context-guarded platform source helper and are
never allocated to tenants, including in deployment reports. These helpers are
not new report keys or public routes; the platform builder phase can compose them.

Tests are in `backend/tests/analytics/test_hi_*_m1f2.py` (ignored by the repository's
existing test ignore rule). Run those three files and the 1f-0 coverage/registry
guards through the isolated runner. The Stage 2 implementer left execution,
reviews, staging and commits to the orchestrator, as requested.
