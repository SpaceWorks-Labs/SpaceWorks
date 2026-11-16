"""Retained fee and remapped provenance must not hide old venue debt. Unrun."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.services import record
from apps.events.booking_decision_service import _fee_state
from apps.events.models import Event
from apps.events.venue_fee_history import history_state
from apps.events import venue_fees
from apps.payments.models import Payment
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db


def make_event(maker, name):
    start = timezone.now() + timedelta(days=2)
    return Event.objects.create(makerspace=maker, title=name, starts_at=start,
                                ends_at=start + timedelta(hours=1), registration_audience="accounts",
                                is_public=True, status="draft")


def test_retained_fee_payment_is_checked_before_unrelated_missing_audit(monkeypatch):
    maker = l6_space("fee-live-first")
    staff, organiser = make_staff(maker), verified("fee-live-payer")
    event = make_event(maker, "Retained")
    fee = venue_fees.configure(event, actor=staff, payer=organiser, mode="custom", basis="flat", amount="10.00")
    Payment.objects.create(makerspace=maker, subject_type="event_venue_fee", subject_id=fee.pk,
                           member=organiser, created_by=staff, amount="10.00", currency="usd")
    monkeypatch.setattr("apps.events.venue_fee_history.history_state", lambda *_: pytest.fail("unneeded audit scan"))
    assert _fee_state(maker, event, lock=False) == "historical_debt"


def test_imported_orphan_subject_collision_does_not_hide_or_reassign_history():
    maker = l6_space("fee-import-collision")
    staff, organiser = make_staff(maker), verified("fee-collision-payer")
    original = make_event(maker, "Original event")
    unrelated = make_event(maker, "Unrelated retained event")
    retained_fee = venue_fees.configure(unrelated, actor=staff, payer=organiser,
                                       mode="custom", basis="flat", amount="10.00")
    # A remapped orphan subject now has the same numeric ID as the unrelated live fee;
    # the separately remapped audit still identifies the original event and payment.
    payment = Payment.objects.create(makerspace=maker, subject_type="event_venue_fee",
        subject_id=retained_fee.pk, member=organiser, created_by=staff, amount="10.00", currency="usd")
    record(staff, "event.venue_fee_charged", makerspace=maker, target=retained_fee,
           meta={"event_id": original.pk, "payment_id": payment.pk, "total": "10.00"})
    assert history_state(maker.pk, original.pk) == "historical_debt"
    # The live numeric collision is deliberately conservative, never a false no-debt.
    assert _fee_state(maker, unrelated, lock=False) == "historical_debt"
    record(staff, "event.venue_fee_charged", makerspace=maker, target=retained_fee,
           meta={"event_id": unrelated.pk, "payment_id": payment.pk, "total": "10.00"})
    assert history_state(maker.pk, original.pk) == "unresolved"


def test_missing_remapped_orphan_provenance_fails_closed():
    maker = l6_space("fee-import-no-provenance")
    staff, organiser = make_staff(maker), verified("fee-unresolved-payer")
    event = make_event(maker, "Event")
    fee = venue_fees.configure(event, actor=staff, payer=organiser, mode="custom", basis="flat", amount="10.00")
    Payment.objects.create(makerspace=maker, subject_type="event_venue_fee", subject_id=fee.pk,
                           member=organiser, created_by=staff, amount="10.00", currency="usd")
    fee.delete()  # A retained payment outlives its optional event fee; no provenance was imported.
    assert history_state(maker.pk, event.pk) == "unresolved"
