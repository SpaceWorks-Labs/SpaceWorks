"""Physical email and room creation cohorts expose every exclusive queue state."""
from datetime import date

import pytest

from apps.integrations.models import EmailLog, NotificationDeliveryLog
from apps.operations.org_reports_messaging import combine_communications
from apps.operations.reports_communications import build_communications_health
from apps.operations.views_report_helpers import date_range_from_dates
from tests.operations.reconciliation_report_helpers import at, delivery, report_space

pytestmark = pytest.mark.django_db
OUTCOMES = ("pending_count", "sending_count", "sent_only_count", "failed_count", "skipped_count", "suppressed_count")


def seed_ledgers(space):
    space.enabled_modules += ["email", "telegram"]
    space.save(update_fields=["enabled_modules"])
    for status in ("pending", "sending", "sent", "failed", "skipped"):
        email = EmailLog.objects.create(makerspace=space, to_email="PRIVATE@example.test",
            subject="PRIVATE SUBJECT", status=status, provider_source="own")
        room = NotificationDeliveryLog.objects.create(makerspace=space, channel="telegram", feature="bookings",
            event="confirmed", text_body="PRIVATE ROOM", status=status)
        for model, row in ((EmailLog, email), (NotificationDeliveryLog, room)):
            model.objects.filter(pk=row.pk).update(created_at=at("2026-10-01T19:00:00"))
    # The email parent is deliberately ignored; the physical email ledger owns it.
    delivery(space, channel="email", state="pending", created=at("2026-10-01T19:00:00"))
    outside = EmailLog.objects.create(makerspace=space, to_email="PRIVATE@example.test",
        subject="PRIVATE", status="pending", provider_source="own")
    EmailLog.objects.filter(pk=outside.pk).update(created_at=at("2026-09-30T19:00:00"))


def test_queued_physical_ledgers_survive_calendar_filters_and_organization_totals():
    first, second = report_space("fr-backlog-first"), report_space("fr-backlog-second")
    seed_ledgers(first)
    seed_ledgers(second)
    window = date_range_from_dates(date(2026, 10, 2), date(2026, 10, 2))
    rows_by_space = []
    for space in (first, second):
        rows = [row for row in build_communications_health(space.pk, date_range=window).records
                if row["channel"] in ("email", "telegram")]
        assert len(rows) == 2
        for row in rows:
            assert row["period"] == "2026-10-02"
            assert row["delivery_count"] == sum(row[key] for key in OUTCOMES) == 5
            assert row["pending_count"] == row["sending_count"] == 1
            assert row["sent_only_count"] == row["failed_count"] == row["skipped_count"] == 1
        rows_by_space.append((space.pk, rows))
    combined = combine_communications(rows_by_space, limit=None)
    assert len(combined) == 2
    for row in combined:
        assert row["delivery_count"] == sum(row[key] for key in OUTCOMES) == 10
        assert row["pending_count"] == row["sending_count"] == 2
    assert "PRIVATE" not in str(combined)
