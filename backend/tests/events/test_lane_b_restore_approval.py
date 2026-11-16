"""Undo retains staff approval but still rechecks admission and the restored FIFO key."""

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events import services
from apps.events.models import EventRegistration, EventTicketType
from apps.events.services_registration_tools import restore_registration
from apps.makerspaces.member_activity_service import _event_registrations
from tests.events.test_lane_b_restore import assert_refusal, cancel, setup_restore
from tests.events.ticketing_helpers import account

pytestmark = pytest.mark.django_db


def test_approved_free_registration_restores_confirmation_without_reapproval(monkeypatch):
    _, staff, _, _, pending = setup_restore(approval=True, capacity=1)
    approved = services.approve_registration(pending, actor=staff)
    cancelled = cancel(approved, staff)
    calls = []
    monkeypatch.setattr(services, "notify_event_lifecycle",
                        lambda event, name, registration_id=None: calls.append((name, registration_id)))
    restored = restore_registration(cancelled, actor=staff)
    assert restored.pk == approved.pk and restored.created_at == approved.created_at
    assert restored.status == "registered" and restored.cancelled_at is None
    assert restored.status_before_cancel == "" and restored.calendar_sequence > cancelled.calendar_sequence
    assert AuditLog.objects.filter(action="event.registration_approved", target_id=str(restored.pk)).count() == 1
    assert AuditLog.objects.get(action="event.registration_restored").actor == staff
    assert calls == [("registration_restored", restored.pk)]


@pytest.mark.parametrize("limit", ["event", "ticket"])
def test_approved_restore_refuses_when_the_event_or_ticket_seat_was_taken(limit):
    space, staff, event, _, pending = setup_restore(approval=True, capacity=1 if limit == "event" else 0)
    ticket = None
    if limit == "ticket":
        ticket = EventTicketType.objects.create(makerspace=space, event=event, name="Free", amount=0, capacity=1)
        pending.ticket_type = ticket
        pending.save(update_fields=["ticket_type"])
    cancelled = cancel(services.approve_registration(pending, actor=staff), staff)
    replacement = services.register(event, member=account("approved-replacement"), actor=staff,
                                    staff_registration=True, ticket_type_id=ticket.pk if ticket else None)
    assert services.approve_registration(replacement, actor=staff).status == "registered"
    assert_refusal(cancelled, staff, "admission_changed")


def test_manually_promoted_approved_waiter_can_restore_confirmation():
    _, staff, event, _, pending = setup_restore(approval=True, capacity=1)
    incumbent = services.approve_registration(pending, actor=staff)
    waiter = services.register(event, member=account("approved-waiter"), actor=staff, staff_registration=True)
    assert services.approve_registration(waiter, actor=staff).status == "waitlisted"
    cancel(incumbent, staff)
    promoted = services.promote_registration(waiter, actor=staff)
    assert restore_registration(cancel(promoted, staff), actor=staff).status == "registered"


def test_approval_from_a_previous_registration_cycle_cannot_bypass_changed_policy():
    _, staff, event, owner, pending = setup_restore(approval=True)
    cancel(services.approve_registration(pending, actor=staff), staff)
    event.registration_requires_approval = False
    event.save(update_fields=["registration_requires_approval"])
    registered = services.register(event, member=owner, actor=staff, staff_registration=True)
    cancelled = cancel(registered, staff)
    event.registration_requires_approval = True
    event.save(update_fields=["registration_requires_approval"])
    assert_refusal(cancelled, staff, "admission_changed")


def test_automatic_promotion_does_not_count_as_staff_approval_after_policy_change():
    _, staff, event, _, incumbent = setup_restore(capacity=1)
    waiter = services.register(event, member=account("automatic-waiter"), actor=staff, staff_registration=True)
    cancel(incumbent, staff)
    waiter.refresh_from_db()
    assert waiter.status == "registered"
    cancelled = cancel(waiter, staff)
    event.registration_requires_approval = True
    event.save(update_fields=["registration_requires_approval"])
    assert_refusal(cancelled, staff, "admission_changed")


def test_dashboard_uses_effective_fifo_time_and_id_tiebreak_for_both_sides():
    _, staff, event, _, _ = setup_restore(capacity=1)
    first = services.register(event, member=account("fifo-first"), actor=staff, staff_registration=True)
    second = services.register(event, member=account("fifo-second"), actor=staff, staff_registration=True)
    third = services.register(event, member=account("fifo-third"), actor=staff, staff_registration=True)
    # Equal effective times still promote by ID. The third row keeps the legacy key.
    common = timezone.now()
    EventRegistration.objects.filter(pk__in=[first.pk, second.pk]).update(waitlist_position_at=common)
    positions = [_event_registrations(event.makerspace, row.member)[0]["waitlist_position"]
                 for row in (first, second, third)]
    assert positions == [2, 3, 1]
    assert EventRegistration.objects.get(pk=first.pk).created_at == first.created_at
