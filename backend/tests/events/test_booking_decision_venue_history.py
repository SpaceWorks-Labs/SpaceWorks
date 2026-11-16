"""Venue-payment evidence distinguishes other events from unresolved history."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.events import venue_fees
from apps.events.models import Event
from apps.events.venue_fee_history import history_state
from apps.payments.services import create_payment
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db(transaction=True)


def _event(maker, title):
    starts = timezone.now() + timedelta(days=2)
    return Event.objects.create(makerspace=maker, title=title, starts_at=starts,
                                ends_at=starts + timedelta(hours=1), registration_audience="accounts", status="draft")


def test_actual_charged_audit_proves_target_and_does_not_block_other_event():
    maker = l6_space("venue-history-known")
    staff, payer = make_staff(maker), verified("venue-history-known-payer")
    first, second = _event(maker, "First"), _event(maker, "Second")
    venue_fees.configure(first, actor=staff, payer=payer, mode="custom", basis="flat", amount=Decimal("10.00"))
    _fee, payment = venue_fees.charge(first, actor=staff)
    assert payment is not None
    assert history_state(maker.pk, first.pk) == "historical_debt"
    assert history_state(maker.pk, second.pk) == "none"


def test_payment_without_charged_audit_is_unresolved():
    maker = l6_space("venue-history-unknown")
    staff, payer = make_staff(maker), verified("venue-history-unknown-payer")
    first, second = _event(maker, "First"), _event(maker, "Second")
    fee = venue_fees.configure(first, actor=staff, payer=payer, mode="custom", basis="flat", amount=Decimal("10.00"))
    create_payment(makerspace=maker, subject_type="event_venue_fee", subject_id=fee.pk,
                   member=payer, amount=Decimal("10.00"), currency="INR", created_by=staff)
    assert history_state(maker.pk, second.pk) == "unresolved"


def test_conflicting_event_audit_for_one_payment_is_unresolved():
    from apps.audit.services import record
    maker = l6_space("venue-history-conflicting")
    staff, payer = make_staff(maker), verified("venue-history-conflicting-payer")
    first, second = _event(maker, "First"), _event(maker, "Second")
    fee = venue_fees.configure(first, actor=staff, payer=payer, mode="custom", basis="flat", amount=Decimal("10.00"))
    _fee, payment = venue_fees.charge(first, actor=staff)
    assert payment is not None
    record(staff, "event.venue_fee_charged", makerspace=maker, target=fee,
           meta={"event_id": second.pk, "payment_id": payment.pk})
    assert history_state(maker.pk, first.pk) == "unresolved"
    assert history_state(maker.pk, second.pk) == "unresolved"


def test_purged_other_event_fee_uses_retained_audit_provenance():
    maker = l6_space("venue-history-purged-other")
    staff, payer = make_staff(maker), verified("venue-history-purged-other-payer")
    first, second = _event(maker, "First"), _event(maker, "Second")
    venue_fees.configure(first, actor=staff, payer=payer, mode="custom", basis="flat", amount=Decimal("10.00"))
    fee, payment = venue_fees.charge(first, actor=staff)
    assert payment is not None
    first.delete()  # The events collector uses Event deletion; the ledger is not an Event FK.
    assert not type(fee).objects.filter(pk=fee.pk).exists()
    assert type(payment).objects.filter(pk=payment.pk).exists()
    assert history_state(maker.pk, second.pk) == "none"


def test_string_event_identifier_is_not_treated_as_typed_audit_proof():
    from apps.audit.services import record
    maker = l6_space("venue-history-invalid-audit")
    staff, payer = make_staff(maker), verified("venue-history-invalid-audit-payer")
    first, second = _event(maker, "First"), _event(maker, "Second")
    fee = venue_fees.configure(first, actor=staff, payer=payer, mode="custom", basis="flat", amount=Decimal("10.00"))
    payment = create_payment(makerspace=maker, subject_type="event_venue_fee", subject_id=fee.pk,
                             member=payer, amount=Decimal("10.00"), currency="INR", created_by=staff)
    record(staff, "event.venue_fee_charged", makerspace=maker, target=fee,
           meta={"event_id": str(first.pk), "payment_id": payment.pk})
    assert history_state(maker.pk, second.pk) == "unresolved"
