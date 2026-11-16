"""L21a attendance confirmation (No -> release or due case, never a refund) and re-accepting a declined place."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events import attendance_confirmation
from apps.events.exceptions import CapacityConflict
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.models import EventAttendanceReply, EventAttendanceRound, EventParticipationSettings, EventRegistration
from apps.events.services_registration_state import reaccept_registration
from apps.payments.models import Payment, RefundCase, RefundPolicy
from tests.events.collab_helpers import client_for, make_event, make_member, make_space, make_staff
from tests.events.test_registration_cancel_api import register

pytestmark = pytest.mark.django_db
FEATURES = ["charges.enabled", "charges.events", "events.attendance_confirmation"]


def world(slug, *, capacity=0, amount=None, free_on_no=False):
    space = make_space(slug)
    space.enabled_features = FEATURES
    space.save(update_fields=["enabled_features"])
    event = make_event(space, is_public=True)
    event.capacity = capacity
    if amount is not None:
        event.payment_amount = Decimal(amount)
    event.save()
    if free_on_no:
        EventParticipationSettings.objects.create(makerspace=space, event=event, attendance_free_on_no=True)
    return space, event, make_staff(space)


def ask(event, staff, members, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        return attendance_confirmation.send(event, actor=staff, kind="confirmation")


def test_staff_send_once_per_12_hours_and_a_reminder_needs_a_first_ask(django_capture_on_commit_callbacks):
    space, event, staff = world("att-send")
    member = make_member(space, "att-a")
    register(event, member)
    with pytest.raises(ProgrammeError) as exc:
        attendance_confirmation.send(event, actor=staff, kind="reminder")
    assert exc.value.detail["code"] == "attendance_not_asked"
    round_ = ask(event, staff, [member], django_capture_on_commit_callbacks)
    round_.refresh_from_db()
    assert round_.recipients == 1 and round_.state == "sent"
    with pytest.raises(ProgrammeError) as exc:
        attendance_confirmation.send(event, actor=staff, kind="reminder")
    assert exc.value.status_code == 429
    EventAttendanceRound.objects.update(created_at=timezone.now() - timedelta(hours=13))
    attendance_confirmation.send(event, actor=staff, kind="reminder")
    assert EventAttendanceRound.objects.filter(event=event).count() == 2


def test_no_with_switch_off_changes_nothing(django_capture_on_commit_callbacks):
    space, event, staff = world("att-off")
    member = make_member(space, "att-b")
    registration = register(event, member)
    ask(event, staff, [member], django_capture_on_commit_callbacks)
    reply = attendance_confirmation.reply(registration, actor=member, answer="no", note="sick")
    registration.refresh_from_db()
    assert reply.effect == "none" and registration.status == "registered"


def test_free_place_released_on_no_promotes_the_waitlist(django_capture_on_commit_callbacks):
    space, event, staff = world("att-free", capacity=1, free_on_no=True)
    first, second = make_member(space, "att-c"), make_member(space, "att-d")
    held, waiting = register(event, first), register(event, second)
    assert waiting.status == "waitlisted"
    ask(event, staff, [first], django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        reply = attendance_confirmation.reply(held, actor=first, answer="no")
    held.refresh_from_db()
    waiting.refresh_from_db()
    assert reply.effect == "released" and held.status == "cancelled" and waiting.status == "registered"
    with pytest.raises(ProgrammeError):
        attendance_confirmation.reply(held, actor=first, answer="yes")


def test_paid_place_on_no_opens_a_due_case_and_moves_no_money(django_capture_on_commit_callbacks):
    space, event, staff = world("att-paid", amount="20", free_on_no=True)
    member = make_member(space, "att-e")
    registration = register(event, member)
    Payment.objects.filter(subject_id=registration.pk, subject_type="event_registration").update(status="paid_offline")
    RefundPolicy.objects.create(makerspace=space, area="events", full_before_minutes=10)
    ask(event, staff, [member], django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        reply = attendance_confirmation.reply(registration, actor=member, answer="no")
    payment = Payment.objects.get(subject_id=registration.pk, subject_type="event_registration")
    assert reply.effect == "due_case" and payment.status == "paid_offline"
    case = RefundCase.objects.get(payment=payment)
    assert case.kind == "due" and case.status not in ("refunded", "settled", "paid")


def test_reply_page_is_the_members_own_and_capability_gated(django_capture_on_commit_callbacks):
    space, event, staff = world("att-api")
    member, other = make_member(space, "att-f"), make_member(space, "att-g")
    register(event, member)
    ask(event, staff, [member], django_capture_on_commit_callbacks)
    url = reverse("events-programme-member-attendance", kwargs={"pk": event.pk})
    assert client_for(other).get(url).status_code == 404
    response = client_for(member).post(url, {"answer": "yes", "note": "see you"}, format="json")
    assert response.status_code == 200 and response.json()["answer"] == "yes"
    roster = client_for(staff).get(reverse("admin-event-registration-list", kwargs={"pk": event.pk}))
    assert roster.status_code == 200
    rows = roster.json()["results"] if isinstance(roster.json(), dict) else roster.json()
    assert rows[0]["attendance_reply"]["answer"] == "yes" and rows[0]["is_crew"] is False
    space.enabled_features = ["charges.enabled"]
    space.save(update_fields=["enabled_features"])
    assert client_for(member).get(url).status_code == 404
    assert EventAttendanceReply.objects.count() == 1


def test_reaccept_declined_respects_capacity_and_charges_after_confirming():
    space, event, staff = world("reaccept", capacity=1, amount="15")
    first, second = make_member(space, "re-a"), make_member(space, "re-b")
    declined = EventRegistration.objects.create(event=event, member=first, name="re-a", email=first.email,
                                                phone="1", status="rejected", quoted_amount=Decimal("15"))
    taken = register(event, second)
    assert taken.status == "registered"
    queued = reaccept_registration(declined, actor=staff)  # parity E-B5 (B16): a full event waitlists, never overbooks
    assert queued.status == "waitlisted" and queued.waitlist_position_at is not None
    assert not Payment.objects.filter(subject_id=declined.pk, subject_type="event_registration").exists()
    EventRegistration.objects.filter(pk=declined.pk).update(status="rejected")
    declined.refresh_from_db()
    EventRegistration.objects.filter(pk=taken.pk).update(status="cancelled")
    row = reaccept_registration(declined, actor=staff)
    assert row.status == "registered"
    payment = Payment.objects.get(subject_id=row.pk, subject_type="event_registration")
    assert payment.status == "pending"  # charged after confirming, through the payment-link path
