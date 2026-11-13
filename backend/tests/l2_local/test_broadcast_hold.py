"""G6 5-second undo hold (#71): cancel inside the hold is the undo; after it, ordinary rules."""
import pytest

from apps.audit.models import AuditLog
from apps.events.models_broadcasts import EventBroadcast
from apps.events.programme.broadcast_schedule import cancel_composer, release_due, send_now
from tests.l2_local.helpers import command, past, previewed, send_payload

pytestmark = pytest.mark.django_db


def test_send_now_holds_five_seconds_and_cancel_inside_is_the_undo(monkeypatch):
    monkeypatch.setattr("apps.events.programme.broadcast_schedule._release_hint", lambda: None)
    space, actor, _member, _event, campaign, preview = previewed(monkeypatch)
    sent = send_now(campaign, actor, send_payload(preview))
    assert sent.status == "scheduled" and sent.undo_hold
    assert 4 <= (sent.available_at - sent.queued_at).total_seconds() <= 6
    assert AuditLog.objects.filter(action="event.broadcast_held", makerspace=space).exists()
    undone = cancel_composer(sent, actor, command(expected_version=sent.version))
    assert undone.status == "cancelled"
    assert AuditLog.objects.filter(action="event.broadcast_cancelled_in_hold").exists()
    release_due(undone.pk)
    undone.refresh_from_db()
    assert undone.status == "cancelled" and not undone.deliveries.exists()


def test_after_the_hold_it_releases_and_a_cancel_is_ordinary(monkeypatch):
    monkeypatch.setattr("apps.events.programme.broadcast_schedule._release_hint", lambda: None)
    _space, actor, _member, _event, campaign, preview = previewed(monkeypatch)
    sent = send_now(campaign, actor, send_payload(preview))
    EventBroadcast.objects.filter(pk=sent.pk).update(available_at=past())
    release_due(sent.pk)
    sent.refresh_from_db()
    assert sent.status == "queued"
    cancelled = cancel_composer(sent, actor, command(expected_version=sent.version))
    assert cancelled.status == "cancelled"
    assert not AuditLog.objects.filter(action="event.broadcast_cancelled_in_hold").exists()
    assert AuditLog.objects.filter(action="event.broadcast.cancelled").exists()
