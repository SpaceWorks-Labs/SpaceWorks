"""Messaging measurement, scope, combination and disclosure contracts (lane 1h-C)."""

import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from itertools import permutations
from types import SimpleNamespace
from uuid import uuid4

import pytest

# Merge decision (2026-10-18 reconciliation, D1 + "reports rebuilt on canonical delivery
# records"): production reporting never reads legacy MessagingDelivery/MessagingConsent.
# Every contract below seeds those retired rows, so it measures nothing real any more.
# The canonical equivalents (monotonic outcomes, billed-zero segments, local grains,
# module gates, consent snapshots, weighted organization rates, platform buckets and
# export disclosure) live in tests/operations/test_reconciliation_communications.py,
# test_reconciliation_report_consent.py, test_reconciliation_platform_reports.py,
# test_reconciliation_report_boundaries.py and test_recon_fr_communications_backlog.py.
pytest.skip("superseded by lane R canonical-delivery report tests (tests/operations/test_reconciliation_*)",
            allow_module_level=True)

from openpyxl import load_workbook  # noqa: E402

from apps.accounts.models import User
from apps.integrations.models import MessagingConsent, MessagingDelivery, MessagingWebhookEvent
from apps.integrations.models_tracking import SmsSendLog
from apps.integrations.reports_communications import CHANNELS, build_communications_health
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.operations import reports
from apps.operations.org_report_aggregate import aggregate_rows
from apps.operations.org_reports import organization_report_data
from apps.operations.platform_scope import _platform_context_for_view
from apps.operations.report_exports import csv_bytes, xlsx_bytes
from apps.operations.report_exports_provenance import build_provenance
from apps.operations.report_date_ranges import CalendarDateRange
from apps.operations.report_fields_hi import MESSAGING_STATUS_COUNTS
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_scope import combined_report_scope
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.encryption.conftest import enabled_encryption
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db
AT = datetime(2026, 10, 11, 20, tzinfo=UTC)


def space(slug):
    row = make_space(slug)
    row.enabled_modules = sorted(set(row.enabled_modules) | {"reports", "sms", "whatsapp"})
    row.timezone = "Asia/Kolkata"
    row.save(update_fields=["enabled_modules", "timezone"])
    return row


def delivery(tenant, user, channel="sms", **values):
    defaults = dict(audience="member", feature="hardware_requests", event="accepted", event_key=str(uuid4()),
                    provider_source="platform", provider="twilio", estimated_segments=1,
                    sender_key="twilio:private_key:+15551234567", context={"body": "private text"})
    row = MessagingDelivery.objects.create(makerspace=tenant, user=user, channel=channel, **(defaults | values))
    MessagingDelivery.objects.filter(pk=row.pk).update(created_at=AT)
    return row


def cohorts(tenant, **kwargs):
    return [r for r in build_communications_health(tenant.pk, **kwargs).records if r["measurement"] == "delivery_cohort"]


@pytest.mark.parametrize("observations,rank,status", [
    (("pending",), 0, "pending"), (("sending",), 0, "sending"),
    (("accepted", "failed"), 1, "failed"), (("failed", "accepted"), 1, "failed"),
    (("sent", "failed"), 2, "failed"), (("failed", "sent"), 2, "failed"),
    (("delivered", "failed"), 3, "delivered"), (("failed", "delivered"), 3, "delivered"),
    (("read",), 4, "read"), (("failed",), 0, "failed"),
])
def test_rank_predicates_measure_persisted_outcome_in_either_order(observations, rank, status):
    tenant = space("m1h-ranks")
    user = make_member("m1h-ranks-user", tenant)
    # Callback order is tested by the transport lane. Analytics consumes its
    # persisted contract, including absent intermediate provider timestamps.
    delivery(tenant, user, progress_rank=rank, status=status,
             failed_at=AT if "failed" in observations else None)
    row, = cohorts(tenant)
    assert [row[f"{metric}_count"] for metric in ("accepted", "sent", "delivered", "read")] == [
        int(rank >= 1), int(rank >= 2), int(rank >= 3), int(rank == 4)]
    assert row["failed_count"] == int(status == "failed")
    assert row["delivery_rate_denominator"] == int(rank >= 1)
    assert row["read_rate_denominator"] == int(rank >= 3)
    assert sum(row[field] for field in MESSAGING_STATUS_COUNTS) == row["delivery_count"]


def test_every_order_of_all_observations_has_identical_cumulative_cohort():
    tenant = space("m1h-permutations")
    user = make_member("m1h-permutations-user", tenant)
    for order in permutations(("accepted", "sent", "delivered", "read", "failed")):
        delivery(tenant, user, event_key="/".join(order), progress_rank=4, status="read", failed_at=AT)
    row, = cohorts(tenant)
    assert all(row[f"{name}_count"] == 120 for name in ("accepted", "sent", "delivered", "read"))
    assert row["failed_count"] == 0
    assert row["delivery_rate"] == row["read_rate"] == 1


@pytest.mark.parametrize("grain,period", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_local_grains_rates_segments_skip_reasons_and_tenant_isolation(grain, period):
    tenant, other = space("m1h-cohorts"), space("m1h-cohorts-other")
    user = make_member("m1h-cohorts-user", tenant)
    for rank, status in ((1, "accepted"), (2, "failed"), (3, "delivered"), (4, "read")):
        delivery(tenant, user, progress_rank=rank, status=status, estimated_segments=3, billed_segments=2)
    delivery(tenant, user, estimated_segments=3, status="skipped", skip_reason="no_consent")
    delivery(tenant, user, status="skipped", skip_reason="quota_exceeded")
    delivery(tenant, user, status="suppressed")
    delivery(other, user, status="read", progress_rank=4)
    rows = cohorts(tenant, grain=grain)
    assert {row["period"] for row in rows} == {period}
    billed = next(r for r in rows if r["segment_source"] == "billed")
    assert (billed["estimated_segments"], billed["billed_segments"], billed["segments"]) == (12, 8, 8)
    assert (billed["delivery_rate_numerator"], billed["delivery_rate_denominator"], billed["delivery_rate"]) == (2, 4, Decimal("0.5"))
    assert (billed["read_rate_numerator"], billed["read_rate_denominator"], billed["read_rate"]) == (1, 2, Decimal("0.5"))
    skipped = {r["skip_reason"]: r for r in rows if r["skipped_count"]}
    assert set(skipped) == {"no_consent", "quota_exceeded"}
    assert skipped["no_consent"]["segments"] == skipped["no_consent"]["estimated_segments"] == 3
    assert skipped["no_consent"]["delivery_rate"] is None
    assert sum(r["delivery_count"] for r in rows) == 7
    assert sum(r["suppressed_count"] for r in rows) == 1


@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_modules_gate_all_rows_including_snapshots_and_abandoned_callbacks(channel):
    tenant = space("m1h-gate")
    user = make_member("m1h-gate-user", tenant)
    delivery(tenant, user, channel=channel)
    for target in (tenant, space("m1h-event-other"), None):
        event = MessagingWebhookEvent.objects.create(makerspace=target, channel=channel, provider="twilio",
            sender_key="private_key", dedupe_id=str(uuid4()), kind="status", state="abandoned")
        MessagingWebhookEvent.objects.filter(pk=event.pk).update(received_at=AT)
    rows = build_communications_health(tenant.pk).records
    assert sum(r["abandoned_webhook_count"] for r in rows if r["channel"] == channel) == 1
    assert channel not in CHANNELS
    tenant.enabled_modules.remove(channel)
    tenant.save(update_fields=["enabled_modules"])
    assert channel not in {r["channel"] for r in build_communications_health(tenant.pk).records}


def test_billed_zero_wins_over_estimate_and_calendar_filters_rebind_locally():
    tenant = space("m1h-billed-zero")
    user = make_member("m1h-billed-zero-user", tenant)
    delivery(tenant, user, billed_segments=0, estimated_segments=3, status="delivered", progress_rank=3)
    dates = CalendarDateRange((datetime(2026, 10, 12, tzinfo=UTC), datetime(2026, 10, 13, tzinfo=UTC)))
    row, = cohorts(tenant, date_range=dates)
    assert row["segment_source"] == "billed" and row["segments"] == 0
    assert row["estimated_segments"] == 3
    assert cohorts(tenant, date_range=tuple(dates)) == []  # Precise instants retain UTC.


def consent(tenant, user, action="opted_in", **values):
    return MessagingConsent.objects.create(makerspace=tenant, user=user, channel="sms", action=action,
        source="member_settings", **({"phone_e164": user.phone_e164, "phone_verified_at": user.phone_verified_at} | values))


def test_consent_is_current_live_snapshot_and_never_an_organization_total():
    a, b = space("m1h-consent-a"), space("m1h-consent-b")
    user = make_member("m1h-consent-user", a)
    user.phone_e164 = "+15551234567"
    user.save(update_fields=["phone_e164"])
    user.phone_verified_at = AT
    user.save(update_fields=["phone_verified_at"])
    MakerspaceMembership.objects.create(user=user, makerspace=b, role="member")
    for tenant in (a, b):
        consent(tenant, user)
    scope = combined_report_scope(Makerspace.objects.filter(pk__in=[a.pk, b.pk]))
    data = organization_report_data(REPORT_REGISTRY["communications-health"], scope, limit=100,
                                    date_range=(AT + timedelta(days=1), None))
    assert data["total"]["rows"] == []
    for breakdown in data["breakdown"]:
        snapshot = next(r for r in breakdown["rows"] if r["channel"] == "sms")
        assert snapshot["consented_member_count"] == 1 and snapshot["period"] is None
    consent(a, user, "opted_out")
    assert next(r for r in build_communications_health(a.pk).records if r["channel"] == "sms")["consented_member_count"] == 0
    user.phone_verified_at = AT + timedelta(seconds=1)  # Same number reverified: prior consent is dead.
    user.save(update_fields=["phone_verified_at"])
    assert next(r for r in build_communications_health(b.pk).records if r["channel"] == "sms")["consented_member_count"] == 0


@pytest.mark.parametrize("refusal", ["revoked", "inactive", "restricted", "changed_phone"])
def test_snapshot_excludes_members_whose_consent_is_no_longer_live(refusal):
    tenant = space("m1h-consent-refusal")
    user = make_member("m1h-consent-refusal-user", tenant)
    user.phone_e164 = "+15551234567"
    user.save(update_fields=["phone_e164"])
    user.phone_verified_at = AT
    user.save(update_fields=["phone_verified_at"])
    consent(tenant, user)
    if refusal == "revoked":
        MakerspaceMembership.objects.filter(makerspace=tenant, user=user).update(status="revoked")
    elif refusal == "inactive":
        User.objects.filter(pk=user.pk).update(is_active=False)
    elif refusal == "restricted":
        User.objects.filter(pk=user.pk).update(access_status="restricted")
    else:
        user.phone_e164 = "+15557654321"
        user.save(update_fields=["phone_e164"])
    row = next(r for r in build_communications_health(tenant.pk).records if r["channel"] == "sms")
    assert row["consented_member_count"] == 0


def test_consent_snapshot_compares_encrypted_phone_through_the_mapper():
    tenant = space("m1h-encrypted-consent")
    user = make_user("m1h-encrypted-user", phone_e164="+15551234567", phone_verified_at=AT)
    MakerspaceMembership.objects.create(user=user, makerspace=tenant, role="member")
    with enabled_encryption():
        entry = consent(tenant, user)
        raw = MessagingConsent.objects.filter(pk=entry.pk).values_list("phone_e164", flat=True).get()
        assert raw.startswith("pii:gcm:v1:")
        rows = build_communications_health(tenant.pk).records
        assert next(r for r in rows if r["channel"] == "sms")["consented_member_count"] == 1
        assert "+15551234567" not in str(rows)


def test_organization_rates_weight_counts_and_preserve_audience_and_source():
    a, b = space("m1h-org-a"), space("m1h-org-b")
    user = make_member("m1h-org-user", a)
    delivery(a, user, channel="whatsapp", status="read", progress_rank=4)
    for _ in range(9):
        delivery(b, user, channel="whatsapp", status="accepted", progress_rank=1)
    delivery(b, user, channel="whatsapp", audience="staff", status="read", progress_rank=4, provider_source="own")
    rows = aggregate_rows("communications-health", [(t.pk, build_communications_health(t.pk).records) for t in (a, b)], limit=100)
    member = next(r for r in rows if r["audience"] == "member")
    assert (member["delivery_rate_numerator"], member["delivery_rate_denominator"], member["delivery_rate"]) == (1, 10, Decimal("0.1"))
    assert member["read_rate"] == 1 and len(rows) == 2
    assert all("consented_member_count" not in r for r in rows)


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_platform_sms_purposes_and_whatsapp_own_counts(grain):
    visible = space("m1h-platform")
    user = make_member("m1h-platform-user", visible)
    operator = make_user("m1h-operator", role=User.Role.SUPERADMIN, access_status="active")
    for tenant in (visible,):
        SmsSendLog.objects.create(makerspace=tenant, status="sent", provider_source="platform")
        for channel in ("sms", "whatsapp"):
            delivery(tenant, user, channel=channel, status="delivered", progress_rank=3)
            delivery(tenant, user, channel=channel, provider_source="own", status="failed")
    ctx = _platform_context_for_view(SimpleNamespace(user=operator))
    data = reports.report_data("platform-services", platform_context=ctx, grain=grain)
    shown = [r for r in data["typed_rows"] if r["makerspace_id"] == visible.pk]
    assert {(r["service"], r["purpose"]) for r in shown} == {("sms", "otp"), ("sms", "notifications"), ("whatsapp", "notifications")}
    assert sum(r["count"] for r in shown if r["provider_source"] == "own") == 2
    assert all(r["amount"] is None for r in shown)
    assert_report_disclosure_safe(data)


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
@pytest.mark.parametrize("key", ["communications-health", "platform-services"])
def test_preview_and_export_are_allowlisted_and_never_disclose_sender_or_content(key, fmt):
    tenant = space("m1h-disclosure")
    user = make_member("m1h-disclosure-user", tenant)
    delivery(tenant, user, feature="api_key=private", audience="secret", provider_source="token",
             skip_reason="password", status="skipped")
    delivery(tenant, user, channel="whatsapp", provider_source="own", status="read", progress_rank=4)
    definition = REPORT_REGISTRY[key]
    ctx = None
    target = tenant.pk
    if definition.platform_only:
        operator = make_user("m1h-export-operator", role=User.Role.SUPERADMIN, access_status="active")
        ctx, target = _platform_context_for_view(SimpleNamespace(user=operator)), None
    data = reports.report_data(key, target, platform_context=ctx)
    matrix = reports.report_rows(key, target, platform_context=ctx)
    assert all(set(row) <= set(definition.fields) for row in data["typed_rows"])
    assert set(matrix[0]) <= set(definition.fields)
    assert_report_disclosure_safe(data)
    provenance = build_provenance(key, version=definition.version, makerspace_id=target, generated_by="builder")
    if fmt == "csv":
        decoded = list(csv.reader(StringIO(csv_bytes(matrix, provenance=provenance).decode().split("\n", 1)[1])))
    else:
        book = load_workbook(BytesIO(xlsx_bytes(matrix, provenance=provenance)), read_only=True)
        decoded = [list(r) for r in book["Report"].iter_rows(values_only=True)]
    assert decoded[0] == list(matrix[0])
    assert_report_disclosure_safe(decoded)
    assert "+15551234567" not in str(decoded) and "private text" not in str(decoded)
    if not definition.platform_only:
        client = authenticated_client(user)
        preview = client.get(f"/api/v1/admin/makerspace/{tenant.pk}/analytics/{key}")
        download = client.get(f"/api/v1/admin/makerspace/{tenant.pk}/reports/{key}/export?format={fmt}")
        assert preview.status_code == download.status_code == 200
        assert_report_disclosure_safe(preview.data)
