# Messaging analytics handoff (1h-C)

`communications-health` v3 composes addressed SMS/WhatsApp facts from
`integrations/reports_messaging.py`. Room `CHANNELS` is unchanged. Each addressed
section requires its own module; neither requires the inbox module. All sources
are explicitly tenant-scoped. Deployment rows retain `makerspace_id`.

## Measurements

Delivery cohorts use `MessagingDelivery.created_at`, bucketed by tenant-local day,
ISO Monday week or month through `period_expression`. Calendar filters rebind to
the tenant timezone; rolling/precise tuple windows keep their instants. Outcomes
are the current recorded outcomes of those creation cohorts, not historical
as-of-window-end reconstructions. Retention limits the available history.

Rows group by period, channel/module, feature, audience and provider source, plus
closed-vocabulary skip reason and segment source. Unknown source values become
`unknown`; no free text, sender identity, provider message ID, phone, body, context,
template name, error code or credential enters the report.

- `accepted_count`: `progress_rank >= 1`.
- `sent_count`: `progress_rank >= 2`, including later undelivered/failed outcomes.
- `delivered_count`: `progress_rank >= 3`.
- `read_count`: `progress_rank == 4`.
- `failed_count`: derived persisted `status == failed`, not `failed_at` presence.
  A delivery/read with a failure observation therefore is not counted as failed.
- `skipped_count`: current skipped outcomes, split by the model's skip-reason
  vocabulary; `suppressed_count` is a separate current outcome.
- `delivery_rate`: delivered / accepted; `read_rate`: read / delivered. Both are
  fractions, null with zero denominators. Each exposes `<rate>_numerator` and
  `<rate>_denominator`. Existing percent fields remain percentages; inbox read
  percentages retain their original read/created definition.
- SMS `estimated_segments` sums local estimates, `billed_segments` sums recorded
  provider bills, and `segments` chooses billed when present (including zero),
  otherwise estimated. `segment_source=billed|estimated` keeps that choice labelled.
  These are recorded segment observations, including any retained estimates on
  skipped rows, not an inferred financial charge. WhatsApp is `not_applicable`.
- `abandoned_webhook_count` counts current abandoned events by receipt cohort
  (`received_at`), in separate `measurement=webhook_receipts` rows. Unattributed
  platform events cannot be guessed onto a tenant. Rejected signatures have no
  durable source in this tree: no zero-valued rejection metric is fabricated.
- `consented_member_count` is a current, date-filter-independent snapshot with
  `measurement=current_consent_snapshot` and `period=null`. It counts active,
  unrestricted local members whose latest ledger row is opted-in and whose phone
  and verification-instance snapshots both still match. Encrypted phones are
  compared through the scoped model mapper with a joined user lookup rather than
  SQL ciphertext comparison or a separate live-consent lookup per member.

`measurement=delivery_cohort` identifies delivery rows. Non-addressed sections use
neutral values for the added dimensions. All new counts/rates are in the public
allowlist and numeric condition registry; previews and CSV/XLSX use the same
disclosure projection. Typed OpenAPI rows are in `serializers_reports_messaging.py`.

## Organization and chart contracts

`org_reports_messaging.combine_communications` group-sums additive observations,
preserving every dimension, and recomputes rates from summed numerators and
denominators. Current consent snapshot rows are excluded entirely from combined
totals, while remaining in tenant breakdowns. The strategy declares the consent
column breakdown-only, because summing it would double-count shared people.

The F1 chart retains its required top-level keys and gains optional per-value
`kind=line|stacked_bar`. Existing values without this property retain their chart
hint. Messaging current outcomes use the exclusive fields `pending_count`,
`sending_count`, `accepted_only_count`, `sent_only_count`, `delivered_only_count`,
`read_count`, `failed_count`, `skipped_count`, `suppressed_count` as stacked bars.
Cumulative sent counts, event overlays and delivery/read ratios are lines.
Dimensions and units must stay separate; cumulative progress must never be stacked.
The backend validator and OpenAPI chart serializer declare the extension. Frontend
rendering of per-value kinds is an integration concern for the frontend lane.

## Platform services

`platform-services` v2 adds `purpose=otp|notifications`: SMS OTP comes only from
`SmsSendLog`, notification SMS/WhatsApp only from `MessagingDelivery`. Logical
delivery rows are counted once, irrespective of retry attempts. Recorded
`provider_source` separates platform and own senders; own usage has counts and
outcomes only, with no segment billing, monetary amounts or configuration reads.
Platform metering retains historical recorded usage even when a tenant module is
now off; source-module associations do not erase those facts.

The existing server-minted PlatformContext remains mandatory. Visible tenants
retain their per-makerspace counts. Hidden platform-provider observations pass
through `hidden_platform_service_bucket`, now also allowing `whatsapp`, and emerge
only as service/day/bucket/count. Tenant ID, outcome, purpose, source and every
other breakdown are absent (null in public matrix projection). Hidden own-provider
usage is excluded, even for an operator with a local membership.

## Integration and verification

No models, migrations or routes were added. Shared generated schema/type and
tenant-dump pins were untouched. Regenerate OpenAPI/TypeScript after integrating
the typed report responses and optional chart value kind. Changed payloads:

- GET `/api/v1/admin/makerspace/{makerspace_id}/analytics/{report_key}`:
  `communications-health`.
- GET `/api/v1/admin/analytics/{report_key}` and
  `/api/v1/admin/reports/{report_key}/export`: communications and platform services.
- GET `/api/v1/admin/makerspace/{makerspace_id}/reports/{report_key}/export`:
  communications export columns.
- GET `/api/v1/admin/platform/analytics/{report_key}`: `platform-services`.
- GET `/api/v1/admin/organizations/{organization_id}/analytics/{report_key}`:
  communications totals/breakdowns and chart value kinds.
- GET `/api/v1/admin/makerspace/{makerspace_id}/reports/catalog`,
  `/api/v1/admin/reports/catalog`, and
  `/api/v1/admin/makerspace/{makerspace_id}/dashboard`: communications fields,
  numeric condition metrics and/or chart value kinds.

Tests: `backend/tests/analytics/test_messaging_reports_m1h.py` and
`test_messaging_report_contract_m1h.py`; existing H/I expectations and the completed
coverage acceptance block were updated. These test paths are repository-ignored:
the orchestrator must include them explicitly. Docker/pytest/review/commits belong
to the orchestrator and were not run by this implementer. Static AST parsing and
whitespace checks are the local verification.
