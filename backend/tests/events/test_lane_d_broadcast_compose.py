"""Draft validation precedes strict mapped reads without bypassing encryption."""

import pytest
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.encryption.crypto import is_envelope
from apps.events.models_broadcasts import EventBroadcast
from apps.events.services_broadcasts import compose
from tests.encryption.conftest import enabled_encryption
from tests.events.collab_helpers import client_for
from tests.events.lane_d_helpers import fixture

pytestmark = pytest.mark.django_db


def test_compose_route_encrypts_draft_with_strict_reads(monkeypatch):
    with enabled_encryption(dual_read=False):
        space, actor, user, event, registration = fixture(monkeypatch)
        subject, body = "Hello {{ name }}", "Private notice for {{ event_title }}"
        response = client_for(actor).post(reverse("admin-event-broadcasts", args=[event.pk]),
            {"subject": subject, "body": body, "statuses": ["registered"]}, format="json")
        assert response.status_code == 201
        assert response.data["subject"] == subject and response.data["body"] == body
        campaign = EventBroadcast.objects.get(pk=response.data["id"])
        assert campaign.status == "draft"
        assert campaign.makerspace_id == space.pk and campaign.created_by_id == actor.pk
        # Inspect stored values before invoking the decrypting model accessor.
        stored = EventBroadcast.objects.filter(pk=campaign.pk).values_list("subject", "body").get()
        assert all(is_envelope(value) for value in stored)
        assert campaign.subject == subject and campaign.body == body
        assert AuditLog.objects.filter(action="event.broadcast.created", makerspace=space).count() == 1


@pytest.mark.parametrize("subject,body,field", [
    ("Bad\nsubject", "Message", "subject"),
    (" " * 3, "Message", "subject"),
    ("s" * 201, "Message", "subject"),
    ("Notice", " ", "body"),
    ("Notice", "b" * 10001, "body"),
    ("Notice", "{{ checkin_token }}", "body"),
    ("Notice", "{% include 'private' %}", "body"),
])
def test_strict_compose_rejects_invalid_input_without_persisting(monkeypatch, subject, body, field):
    with enabled_encryption(dual_read=False):
        space, actor, user, event, registration = fixture(monkeypatch)
        with pytest.raises(ValidationError) as error:
            compose(event, actor, subject=subject, body=body, statuses=["registered"])
        assert field in error.value.detail
        assert not EventBroadcast.objects.filter(event=event).exists()
        assert not AuditLog.objects.filter(action="event.broadcast.created", makerspace=space).exists()
