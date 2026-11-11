"""G7 approval digest: one per organiser per 30-minute window, counts only, skipped when idle."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.approval_digest import digest_eligible, send_approval_digests_task, send_for_space, window_start
from apps.events.services_registration import register
from apps.integrations.models_contract import NotificationEnvelope
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import account, event_space, open_event
from tests.l2_local.helpers import off, on

pytestmark = pytest.mark.django_db


def pending_space():
    space = event_space("digest")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications", "email"})
    space.save(update_fields=["enabled_modules"])
    staff = make_staff(space)
    event = open_event(space, registration_requires_approval=True)
    member = account("waiting")
    row = register(event, member=member, actor=member)
    assert row.status == "pending_approval"
    return space, staff, event


def digests():
    return NotificationEnvelope.objects.filter(source_kind="events.approval_digest")


def test_off_sends_nothing_and_on_sends_one_per_window():
    space, staff, event = pending_space()
    off(space, "events.approval_digest")
    assert send_for_space(space) == 0 and not digests().exists()
    on(space, "events.approval_digest")
    assert send_for_space(space) >= 1
    assert send_for_space(space) >= 1  # same window: dedup key, no second envelope
    envelope = digests().get(recipient=staff)
    assert envelope.context["event_ids"] == [event.pk]
    assert "waiting" not in envelope.context  # no names, counts are in the encrypted body only
    assert digest_eligible(envelope)
    assert AuditLog.objects.filter(action="event.approval_digest_sent", makerspace=space).exists()


def test_nothing_waiting_sends_nothing_and_a_decision_makes_it_stale():
    space, staff, event = pending_space()
    on(space, "events.approval_digest")
    send_for_space(space)
    envelope = digests().get(recipient=staff)
    event.registrations.update(status="registered")
    assert not digest_eligible(envelope)
    later = timezone.now() + timedelta(minutes=31)
    assert send_for_space(space, later) == 0
    assert window_start(later) != window_start(timezone.now())


def test_task_is_bounded_and_counts():
    space, _staff, _event = pending_space()
    on(space, "events.approval_digest")
    result = send_approval_digests_task()
    assert result["sent"] >= 1 and result["failed"] == 0
