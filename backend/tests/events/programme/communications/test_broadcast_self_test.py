"""Test recipient identity is server-owned and eligibility survives retries."""

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.events.programme.broadcast_preview import create_preview
from apps.events.programme.broadcast_test import prepare_test, test_self as send_self_test
from apps.integrations.delivery_content import content
from apps.integrations.models import EmailLog
from tests.events.lane_d_helpers import fixture
from tests.events.programme.communications.test_broadcast_schedule import command, composer

pytestmark = pytest.mark.django_db


def test_self_test_queues_only_verified_actor_and_replays_once(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    actor.email_verified_at = timezone.now()
    actor.save(update_fields=["email_verified_at"])
    campaign = composer(event, actor)
    preview = create_preview(campaign, actor, command())
    payload = command(preview_id=preview["preview_id"])
    result = send_self_test(campaign, actor, payload)
    assert result["recipient"] == "self"
    assert send_self_test(campaign, actor, payload) == result
    logs = EmailLog.objects.filter(source_kind="events.broadcast_test")
    assert logs.count() == 1
    log = logs.get()
    assert result["id"] == log.pk and result["event_id"] == event.pk
    assert result["version"] == campaign.version and result["allowed_actions"] == []
    assert log.recipient_id == actor.pk and log.to_email == actor.email
    assert prepare_test(log)
    assert content(log).subject.startswith("[Test]")
    assert "Space Works" in content(log).html_body
    assert member.email not in content(log).text_body
    assert str(registration.checkin_token) not in str(content(log))
    actor.is_active = False
    actor.save(update_fields=["is_active"])
    assert not prepare_test(log)


def test_unverified_self_test_is_not_persisted(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    actor.email_verified_at = None
    actor.save(update_fields=["email_verified_at"])
    campaign = composer(event, actor)
    preview = create_preview(campaign, actor, command())
    with pytest.raises(ValidationError):
        send_self_test(campaign, actor, command(preview_id=preview["preview_id"]))
    assert not EmailLog.objects.filter(source_kind="events.broadcast_test").exists()


@pytest.mark.parametrize("invalidate", ["email", "event", "cancel", "feature", "module"])
def test_test_source_live_invalidation(monkeypatch, invalidate):
    space, actor, member, event, registration = fixture(monkeypatch)
    actor.email_verified_at = timezone.now()
    actor.save(update_fields=["email_verified_at"])
    campaign = composer(event, actor)
    preview = create_preview(campaign, actor, command())
    send_self_test(campaign, actor, command(preview_id=preview["preview_id"]))
    log = EmailLog.objects.get(source_kind="events.broadcast_test")
    if invalidate == "email":
        actor.email = "changed@example.test"
        actor.save(update_fields=["email"])
    elif invalidate == "event":
        event.title = "Different event details"
        event.save(update_fields=["title"])
    elif invalidate == "cancel":
        from apps.events.programme.broadcast_schedule import cancel_composer
        cancel_composer(campaign, actor, command(expected_version=campaign.version))
    elif invalidate == "feature":
        space.enabled_features.remove("events.broadcasts")
        space.save(update_fields=["enabled_features"])
    else:
        space.enabled_modules.remove("notifications")
        space.save(update_fields=["enabled_modules"])
    assert not prepare_test(log)


def test_personal_source_rejects_stale_revision_and_withdrawn_sender(monkeypatch):
    from datetime import timedelta
    from apps.events.broadcast_channels import personal_source_eligible
    from apps.events.models_broadcasts import EventBroadcast
    from apps.events.programme.broadcast_schedule import release_due, schedule
    from apps.integrations.broadcasts_worker import broadcast_batch
    from apps.integrations.models_contract import NotificationEnvelope
    from tests.events.programme.communications.test_broadcast_schedule import confirm
    space, actor, member, event, registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    campaign = schedule(campaign, actor, confirm(create_preview(campaign, actor, command())))
    EventBroadcast.objects.filter(pk=campaign.pk).update(available_at=timezone.now() - timedelta(seconds=1))
    release_due(campaign.pk)
    broadcast_batch("event_broadcast", campaign.pk)
    envelope = NotificationEnvelope.objects.get(source_kind="events.broadcast", recipient=member)
    assert personal_source_eligible(envelope)
    revision = envelope.revision
    envelope.revision = "0" * 64
    assert not personal_source_eligible(envelope)
    envelope.revision = revision
    actor.is_active = False
    actor.save(update_fields=["is_active"])
    assert not personal_source_eligible(envelope)
