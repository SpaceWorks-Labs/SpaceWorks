"""BK-0 fixtures keep debt tracking independent of a configured payment rail."""

import pytest

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.payments.models import Payment
from tests.payments.test_track3_booking_event_charging import (
    bookable, create_booking, member_with_phone,
)
from tests.return_helpers import make_space


@pytest.fixture
def ledger_booking():
    makerspace = make_space("bk0-ledger")
    makerspace.enabled_modules = ["bookings"]
    makerspace.enabled_features = ["charges.enabled", "charges.bookings", "bookings.recurring"]
    makerspace.save(update_fields=["enabled_modules", "enabled_features"])
    manager = member_with_phone("bk0-manager", makerspace)
    member = member_with_phone("bk0-member", makerspace)
    return makerspace, bookable(makerspace), member, manager


def ledger_state():
    """Compare persisted rows, including calendar timestamps and payment metadata."""
    return (
        list(Booking.objects.order_by("pk").values()),
        list(Payment.objects.order_by("pk").values()),
        list(AuditLog.objects.order_by("pk").values()),
    )


def fail_ledger(monkeypatch, operation):
    """Fail real ORM writes/audits after they happened, or the actual subject lookup."""
    if operation == "lookup":
        from django.db.models.query import QuerySet

        original = QuerySet.first

        def first(queryset):
            if queryset.model is Payment:
                raise RuntimeError("required ledger lookup failed")
            return original(queryset)

        monkeypatch.setattr(QuerySet, "first", first)
    elif operation == "write":
        original = Payment.save

        def save(payment, *args, **kwargs):
            original(payment, *args, **kwargs)
            raise RuntimeError("required ledger write failed")

        monkeypatch.setattr(Payment, "save", save)
    else:
        from apps.audit import services as audit

        original = audit.record

        def record(actor, action, **kwargs):
            result = original(actor, action, **kwargs)
            if action in {"payment.created", "payment.canceled"}:
                raise RuntimeError("required ledger audit failed")
            return result

        monkeypatch.setattr(audit, "record", record)
