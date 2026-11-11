"""B16/C22: re-accept waitlists when full; the 24-hour pay window releases an unpaid place to the next person."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events import pay_window, services
from apps.events.models import EventRegistration
from apps.events.services_registration_state import reaccept_registration
from apps.payments.models import Payment
from tests.events.collab_helpers import make_member
from tests.events.test_registration_cancel_api import register
from tests.parity_0120.e_b5.helpers import world

pytestmark = pytest.mark.django_db
SUBJECT = Payment.SubjectType.EVENT_REGISTRATION


def charge(registration):
    return Payment.objects.get(subject_id=registration.pk, subject_type=SUBJECT)


def test_reaccept_when_full_joins_the_tail_of_the_waitlist_and_is_not_charged():
    space, event, staff = world("pw-a", capacity=1, amount="15")
    first, second = make_member(space, "pw-first"), make_member(space, "pw-second")
    declined = EventRegistration.objects.create(event=event, member=first, name="f", email=first.email, phone="1",
                                                status="rejected", quoted_amount=Decimal("15"))
    register(event, second)
    queued = reaccept_registration(declined, actor=staff)
    assert queued.status == "waitlisted" and queued.waitlist_position_at is not None
    assert not Payment.objects.filter(subject_id=declined.pk, subject_type=SUBJECT).exists()


def test_promotion_opens_a_window_only_when_the_switch_is_on():
    space, event, staff = world("pw-b", "events.pay_window", capacity=1, amount="15")
    a, b = make_member(space, "pw-a1"), make_member(space, "pw-b1")
    first, waiting = register(event, a), register(event, b)
    assert waiting.status == "waitlisted"
    services.cancel_registration(first, actor=staff)
    waiting.refresh_from_db()
    assert waiting.status == "registered" and waiting.pay_by is not None
    assert abs(waiting.pay_by - (timezone.now() + pay_window.WINDOW)) < timedelta(minutes=1)
    assert AuditLog.objects.filter(action="event.registration.pay_window_opened").exists()

    space.enabled_features = [key for key in space.enabled_features if key != "events.pay_window"]
    space.save(update_fields=["enabled_features"])
    EventRegistration.objects.filter(pk=waiting.pk).update(pay_by=timezone.now() - timedelta(minutes=1))
    assert pay_window.due(10) == []  # off means no scheduled work


def test_an_expired_window_voids_the_charge_releases_the_place_and_promotes_the_next():
    space, event, staff = world("pw-c", "events.pay_window", capacity=1, amount="15")
    a, b, c = (make_member(space, f"pw-{n}") for n in "abc")
    first, second, third = register(event, a), register(event, b), register(event, c)
    services.cancel_registration(first, actor=staff)
    second.refresh_from_db()
    assert second.pay_by is not None and charge(second).status == "pending"
    EventRegistration.objects.filter(pk=second.pk).update(pay_by=timezone.now() - timedelta(minutes=1))
    assert pay_window.due(10) == [second.pk]
    assert pay_window.expire(second.pk) is True
    second.refresh_from_db()
    third.refresh_from_db()
    assert second.status == "cancelled" and second.pay_by is None
    assert charge(second).status == "canceled"  # voided through payments; the ledger row stays
    assert third.status == "registered" and third.pay_by is not None
    assert AuditLog.objects.filter(action="event.registration.pay_window_expired").count() == 1


def test_a_settled_charge_clears_the_window_instead_of_releasing():
    space, event, staff = world("pw-d", "events.pay_window", capacity=1, amount="15")
    a, b = make_member(space, "pw-s1"), make_member(space, "pw-s2")
    first, second = register(event, a), register(event, b)
    services.cancel_registration(first, actor=staff)
    second.refresh_from_db()
    Payment.objects.filter(subject_id=second.pk, subject_type=SUBJECT).update(status="succeeded")
    EventRegistration.objects.filter(pk=second.pk).update(pay_by=timezone.now() - timedelta(minutes=1))
    assert pay_window.expire(second.pk) is False
    second.refresh_from_db()
    assert second.status == "registered" and second.pay_by is None
