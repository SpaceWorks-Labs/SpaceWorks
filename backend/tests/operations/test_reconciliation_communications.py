"""Canonical messaging history, current sender proof and local-calendar reports."""
from datetime import date
from decimal import Decimal

import pytest

from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.models_cutover import NotificationIngress
from apps.integrations.models_cutover import NotificationLegacyMapping
from apps.integrations.models_messaging_delivery import MessagingDelivery
from apps.integrations.reports_messaging import build_messaging, messaging_row
from apps.operations.org_reports_messaging import combine_communications
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.reports_notification_facts import delivery_facts
from apps.operations.views_report_helpers import date_range_from_dates
from tests.operations.reconciliation_report_helpers import at, delivery, report_space

pytestmark = pytest.mark.django_db


def cohorts(space, **kwargs):
    return [row for row in build_messaging(space.pk, **kwargs).records if row["measurement"] == "delivery_cohort"]


def test_canonical_history_is_counted_once_with_progress_segments_and_held_outcomes():
    space = report_space("recon-r-history")
    read = delivery(space, state="read", attempt_count=1, estimated_segments=3, billed_segments=0)
    delivery(space, state="failed", attempt_count=2, estimated_segments=2,
        history={"progress_rank": 2, "status": "failed", "context": {"phone": "PRIVATE PHONE"}})
    delivery(space, state="held", attempt_count=1)
    # Frozen old records cannot contribute a second copy of mapped history.
    MessagingDelivery.objects.create(makerspace=space, user=read.envelope.recipient, channel="sms",
        event_key="old", feature="bookings", event="confirmed", audience="member", status="read", progress_rank=4)
    rows = cohorts(space)
    assert sum(row["delivery_count"] for row in rows) == 3
    assert sum(row["accepted_count"] for row in rows) == 2
    assert sum(row["sent_count"] for row in rows) == 2
    assert sum(row["delivered_count"] for row in rows) == 1
    assert sum(row["read_count"] for row in rows) == 1
    assert sum(row["failed_count"] for row in rows) == 1
    assert sum(row["held_count"] for row in rows) == 1
    assert sum(row["attempt_count"] for row in rows) == 4
    billed = next(row for row in rows if row["segment_source"] == "billed")
    assert billed["estimated_segments"] == 3 and billed["segments"] == billed["billed_segments"] == 0
    assert sum(row["segments"] for row in rows) == 2
    assert all(row["audience"] == "requester" for row in rows)
    assert "PRIVATE" not in str(rows)


def test_late_failure_cannot_erase_delivered_history_and_provider_text_is_closed():
    space = report_space("recon-r-monotonic")
    row = delivery(space, state="failed", delivered_at=at("2026-10-01T10:00:00"),
                   last_error="PRIVATE PHONE AND ERROR")
    fact = next(delivery_facts(NotificationDelivery.objects.filter(pk=row.pk)))
    assert fact["progress"] == 3 and fact["status"] == "delivered"
    skipped = delivery(space, state="skipped", last_error="PRIVATE PHONE AND ERROR")
    rows = cohorts(space)
    assert next(r for r in rows if r["skipped_count"])["skip_reason"] == "unknown"
    assert "PRIVATE" not in str(rows)
    skipped.refresh_from_db()
    assert skipped.state == "skipped"  # Reporting does not reconcile/mutate sources.


def test_mapped_suppression_and_canceled_queue_remain_distinct_history():
    space = report_space("recon-r-dispositions")
    row = delivery(space, state="skipped", last_error="no_consent",
                   history={"status": "suppressed", "progress_rank": 0, "skip_reason": "no_consent"})
    delivery(space, state="skipped", last_error="migration_cancelled")
    rows = cohorts(space)
    assert sum(r["suppressed_count"] for r in rows) == 1
    assert sum(r["skipped_count"] for r in rows) == 1
    assert sum(r["pending_count"] for r in rows) == 0
    assert row.attempt_count == 0


def test_T_foundation_mapping_preserves_progress_from_before_timestamp_expansion():
    import json
    from apps.makerspaces.secrets import encrypt_value
    space = report_space("recon-r-t-foundation")
    row = delivery(space, state="failed")
    NotificationLegacyMapping.objects.create(makerspace=space, legacy_model="NotificationDelivery.T", legacy_id=row.pk,
        canonical_model="NotificationDelivery", canonical_id=row.pk, disposition="canonical_foundation",
        snapshot=encrypt_value(json.dumps({"state": "accepted"})))
    measured = cohorts(space)
    assert measured[0]["accepted_count"] == measured[0]["failed_count"] == 1


def test_calendar_window_uses_each_tenants_local_dst_boundaries():
    ny = report_space("recon-r-ny", zone="America/New_York")
    india = report_space("recon-r-india")
    for space in (ny, india):
        for segments, instant in enumerate(("2026-03-08T04:59:59", "2026-03-08T05:00:00", "2026-03-09T03:59:59", "2026-03-09T04:00:00"), 1):
            delivery(space, created=at(instant), estimated_segments=segments)
    window = date_range_from_dates(date(2026, 3, 8), date(2026, 3, 8))
    assert sum(r["delivery_count"] for r in cohorts(ny, date_range=window)) == 2
    assert sum(r["delivery_count"] for r in cohorts(india, date_range=window)) == 2
    assert sum(r["segments"] for r in cohorts(ny, date_range=window)) == 5
    assert sum(r["segments"] for r in cohorts(india, date_range=window)) == 3
    aggregate = [r for r in build_messaging(None, date_range=window).records if r["delivery_count"]]
    assert {r["makerspace_id"] for r in aggregate} == {ny.pk, india.pk}
    assert {r["period"] for r in aggregate} == {"2026-03-08"}


def test_held_receipts_are_not_reported_as_abandoned_or_applied():
    space = report_space("recon-r-receipts")
    receipt = NotificationIngress.objects.create(makerspace=space, channel="sms", provider="twilio",
        sender_key="PRIVATE SENDER", dedupe_key="r-receipt", payload="PRIVATE CIPHERTEXT", state="held")
    rows = build_messaging(space.pk).records
    measured = next(row for row in rows if row["measurement"] == "webhook_receipts")
    assert measured["held_webhook_count"] == 1 and measured["abandoned_webhook_count"] == 0
    receipt.refresh_from_db()
    assert receipt.state == "held" and "PRIVATE" not in str(rows)


def test_original_abandoned_receipt_history_survives_replay_without_reading_frozen_events():
    import json
    from apps.makerspaces.secrets import encrypt_value
    space = report_space("recon-r-receipt-history")
    NotificationLegacyMapping.objects.create(makerspace=space, legacy_model="MessagingWebhookEvent", legacy_id=19,
        canonical_model="NotificationIngress", canonical_id=100, disposition="replay_required",
        snapshot=encrypt_value(json.dumps({"channel": "sms", "state": "abandoned",
            "received_at": "2026-03-07T19:00:00+00:00", "payload": "PRIVATE MESSAGE"})))
    window = date_range_from_dates(date(2026, 3, 8), date(2026, 3, 8))
    rows = build_messaging(space.pk, date_range=window).records
    assert sum(row["abandoned_webhook_count"] for row in rows) == 1
    assert sum(row["held_webhook_count"] for row in rows) == 0
    assert "PRIVATE" not in str(rows)


def test_organization_totals_recompute_rates_and_exclude_current_person_snapshot():
    first = messaging_row("sms", period="2026-10-01", accepted_count=2, delivered_count=1,
        delivery_rate_numerator=1, delivery_rate_denominator=2, held_count=1)
    second = messaging_row("sms", period="2026-10-01", accepted_count=8, delivered_count=6,
        delivery_rate_numerator=6, delivery_rate_denominator=8, held_count=2)
    snapshot = messaging_row("sms", measurement="current_consent_snapshot", consented_member_count=99)
    rows = combine_communications([(1, [first, snapshot]), (2, [second, snapshot])], limit=None)
    assert len(rows) == 1 and rows[0]["delivery_rate"] == Decimal("0.7000")
    assert rows[0]["held_count"] == 3 and "consented_member_count" not in rows[0]


def test_registry_uses_canonical_builder_and_exclusive_outcome_chart():
    definition = REPORT_REGISTRY["communications-health"]
    assert definition.builder_path == "apps.operations.reports_communications.build_communications_health"
    assert definition.version == 4
    values = definition.chart_spec["values"]
    assert next(v for v in values if v["field"] == "held_count")["kind"] == "stacked_bar"
    assert next(v for v in values if v["field"] == "delivery_rate")["kind"] == "line"
    assert not any(v["field"] in {"accepted_count", "delivered_count"} and v.get("kind") == "stacked_bar" for v in values)
