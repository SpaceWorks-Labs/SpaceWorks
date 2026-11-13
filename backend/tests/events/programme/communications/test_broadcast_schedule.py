"""Immutable preview, deadline, cancellation and restart regressions for G's DB run."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events.models_broadcasts import EventBroadcast, EventBroadcastPreview
from apps.events.programme.broadcast_preview import create_composer, create_preview, preview_response
from apps.events.programme.broadcast_schedule import cancel_composer, release_due, resume_scheduled_broadcasts, schedule
from apps.events.programme.commands import ProgrammeConflict
from apps.events.services_broadcasts import change
from apps.integrations.broadcasts_worker import broadcast_batch
from tests.events.lane_d_helpers import fixture

pytestmark = pytest.mark.django_db


def composer(event, actor):
    return create_composer(event, actor, {"subject": "A maker update", "body": "Welcome {{ name }}",
        "statuses": ["registered"], "attendance": "any", "render_schema_version": 2,
        "design": "classic", "ctas": [{"kind": "navigation", "label": "Ticket", "target": "ticket"}]}, uuid4())


def command(**values):
    return {"operation_id": uuid4(), "expected_version": 1, **values}


def confirm(preview, **values):
    return command(preview_id=preview["preview_id"], revision=preview["revision"],
        recipient_count=preview["recipient_count"], confirm=True,
        available_at=timezone.now() + timedelta(minutes=1), **values)


def test_preview_is_immutable_replayable_and_content_is_encrypted(monkeypatch):
    from tests.encryption.conftest import enabled_encryption
    from apps.encryption.crypto import is_envelope
    with enabled_encryption(dual_read=False):
        space, actor, member, event, registration = fixture(monkeypatch)
        campaign = composer(event, actor)
        request = command()
        preview = create_preview(campaign, actor, request)
        assert create_preview(campaign, actor, request) == preview
        assert EventBroadcastPreview.objects.filter(campaign=campaign).count() == 1
        assert preview["recipient_count"] == 1
        assert preview["id"] == preview["preview_id"]
        assert preview["event_id"] == event.pk and preview["version"] == campaign.version
        assert preview["state"] == "ready" and preview["allowed_actions"] == ["test", "schedule"]
        assert "max-width:640px" in preview["desktop_html"]
        assert "max-width:360px" in preview["mobile_html"]
        row = EventBroadcastPreview.objects.get(pk=preview["preview_id"])
        row.recipient_count = 100
        with pytest.raises(DjangoValidationError):
            row.save()
        raw_body = EventBroadcast.objects.filter(pk=campaign.pk).values_list("body", flat=True).get()
        assert is_envelope(raw_body)
        assert "Welcome" not in raw_body and "Ticket" not in raw_body
        assert not campaign.deliveries.exists()
        assert AuditLog.objects.filter(action="event.broadcast.previewed", makerspace=space).count() == 1


def test_deadline_and_confirmation_cannot_be_bypassed_by_old_queue(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    preview = create_preview(campaign, actor, command())
    with pytest.raises(ValidationError):
        change(campaign, actor, "queue")
    values = confirm(preview)
    values["available_at"] = timezone.now() + timedelta(seconds=4)
    with pytest.raises(ValidationError):
        schedule(campaign, actor, values)
    values = confirm(preview)
    values["confirm"] = False
    with pytest.raises(ValidationError):
        schedule(campaign, actor, values)
    assert not campaign.deliveries.exists()


def test_changed_audience_refuses_stale_selection(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    preview = create_preview(campaign, actor, command())
    type(registration).objects.filter(pk=registration.pk).update(status="cancelled")
    with pytest.raises(ProgrammeConflict):
        schedule(campaign, actor, confirm(preview))
    campaign.refresh_from_db()
    assert campaign.status == "draft"


def test_early_worker_restart_cancel_and_later_recovery(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    preview = create_preview(campaign, actor, command())
    values = confirm(preview)
    campaign = schedule(campaign, actor, values)
    assert schedule(campaign, actor, values).pk == campaign.pk
    assert campaign.status == "scheduled"
    scheduled_preview = preview_response(EventBroadcastPreview.objects.get(pk=preview["preview_id"]), actor)
    assert scheduled_preview["state"] == "scheduled" and scheduled_preview["allowed_actions"] == []
    broadcast_batch("event_broadcast", campaign.pk)
    release_due(campaign.pk)
    campaign.refresh_from_db()
    assert campaign.status == "scheduled" and not campaign.deliveries.exists()
    campaign = cancel_composer(campaign, actor, command(expected_version=campaign.version))
    EventBroadcast.objects.filter(pk=campaign.pk).update(available_at=timezone.now() - timedelta(seconds=1))
    resume_scheduled_broadcasts()
    campaign.refresh_from_db()
    assert campaign.status == "cancelled" and not campaign.deliveries.exists()
    assert cancel_composer(campaign, actor, command(expected_version=campaign.version)).status == "cancelled"

    second = composer(event, actor)
    second = schedule(second, actor, confirm(create_preview(second, actor, command())))
    EventBroadcast.objects.filter(pk=second.pk).update(available_at=timezone.now() - timedelta(seconds=1))
    # This path does not depend on any original Celery timer surviving.
    resume_scheduled_broadcasts()
    broadcast_batch("event_broadcast", second.pk)
    second.refresh_from_db()
    assert second.status == "sending" and second.deliveries.count() == 1


def test_original_sender_withdrawal_cancels_scheduled_campaign(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    campaign = schedule(campaign, actor, confirm(create_preview(campaign, actor, command())))
    EventBroadcast.objects.filter(pk=campaign.pk).update(available_at=timezone.now() - timedelta(seconds=1))
    actor.is_active = False
    actor.save(update_fields=["is_active"])
    resume_scheduled_broadcasts()
    campaign.refresh_from_db()
    assert campaign.status == "cancelled" and not campaign.deliveries.exists()


def test_cancel_after_due_release_still_stops_unclaimed_worker(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    campaign = schedule(campaign, actor, confirm(create_preview(campaign, actor, command())))
    EventBroadcast.objects.filter(pk=campaign.pk).update(available_at=timezone.now() - timedelta(seconds=1))
    release_due(campaign.pk)
    campaign.refresh_from_db()
    assert campaign.status == "queued"
    cancel_composer(campaign, actor, command(expected_version=campaign.version))
    broadcast_batch("event_broadcast", campaign.pk)
    assert not campaign.deliveries.exists()


def test_provider_acceptance_is_not_recalled(monkeypatch):
    from apps.integrations.dispatch_delivery import _deliver
    from tests.events.lane_d_helpers import smtp
    space, actor, member, event, registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    campaign = schedule(campaign, actor, confirm(create_preview(campaign, actor, command())))
    EventBroadcast.objects.filter(pk=campaign.pk).update(available_at=timezone.now() - timedelta(seconds=1))
    release_due(campaign.pk)
    broadcast_batch("event_broadcast", campaign.pk)
    delivery = campaign.deliveries.get()
    accepted = smtp(monkeypatch)
    _deliver(delivery.outbox)
    campaign.refresh_from_db()
    assert accepted.call_count == 1 and campaign.status == "sent"
    with pytest.raises(ValidationError):
        cancel_composer(campaign, actor, command(expected_version=campaign.version))
    assert accepted.call_count == 1


def test_cancel_service_requires_cas_and_replays_without_second_mutation(monkeypatch):
    space, actor, member, event, registration = fixture(monkeypatch)
    campaign = composer(event, actor)
    with pytest.raises(ValidationError):
        change(campaign, actor, "cancel")
    with pytest.raises(ProgrammeConflict):
        cancel_composer(campaign, actor, command(expected_version=campaign.version + 1))
    campaign.refresh_from_db()
    assert campaign.status == "draft" and campaign.version == 1
    payload = command()
    cancelled = cancel_composer(campaign, actor, payload)
    assert cancelled.status == "cancelled" and cancelled.version == 2
    replay = cancel_composer(campaign, actor, payload)
    assert replay.status == "cancelled" and replay.version == 2
    assert AuditLog.objects.filter(action="event.broadcast.cancelled", makerspace=space).count() == 1
    with pytest.raises(ProgrammeConflict):
        cancel_composer(campaign, actor, command())


def test_cancel_http_requires_v2_command_and_preserves_v1_empty_body(monkeypatch):
    from django.urls import reverse
    from tests.events.collab_helpers import client_for
    from apps.events.services_broadcasts import compose
    space, actor, member, event, registration = fixture(monkeypatch)
    client = client_for(actor)
    campaign = composer(event, actor)
    url = reverse("admin-event-broadcast-cancel", args=[event.pk, campaign.pk])
    assert client.post(url, {}, format="json").status_code == 400
    stale = {"operation_id": str(uuid4()), "expected_version": 2}
    assert client.post(url, stale, format="json").status_code == 409
    payload = {"operation_id": str(uuid4()), "expected_version": 1}
    response = client.post(url, payload, format="json")
    assert response.status_code == 200 and response.data["status"] == "cancelled"
    assert client.post(url, payload, format="json").data == response.data
    conflict = client.post(url, {**payload, "expected_version": 2}, format="json")
    assert conflict.status_code == 409 and conflict.data["code"] == "idempotency_conflict"
    assert AuditLog.objects.filter(action="event.broadcast.cancelled", makerspace=space).count() == 1
    legacy = compose(event, actor, subject="Legacy", body="Notice", statuses=["registered"])
    legacy_url = reverse("admin-event-broadcast-cancel", args=[event.pk, legacy.pk])
    assert client.post(legacy_url, {}, format="json").status_code == 200
