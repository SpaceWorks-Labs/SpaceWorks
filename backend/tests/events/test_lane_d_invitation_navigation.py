"""Invitation mail must navigate to an accessible public event detail."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.utils import timezone

from apps.events.services_bulk_invites import bulk_invites
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from tests.events.collab_helpers import client_for
from tests.events.lane_d_helpers import fixture, smtp
from tests.events.ticketing_helpers import public_url

pytestmark = pytest.mark.django_db


def make_inaccessible(event, reason):
    if reason == "private":
        event.is_public = False
    elif reason == "ended":
        event.starts_at = timezone.now() - timedelta(hours=2)
        event.ends_at = timezone.now() - timedelta(hours=1)
    else:
        event.status = reason
    event.save(update_fields=["is_public", "status", "starts_at", "ends_at"])


@pytest.mark.parametrize("reason", ["private", "draft", "cancelled", "ended"])
def test_inaccessible_event_rejects_mail_before_creating_invites(monkeypatch, reason):
    _, actor, user, event, _ = fixture(monkeypatch)
    make_inaccessible(event, reason)
    enqueue = Mock()
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", enqueue)

    response = client_for(actor).post(reverse("admin-event-bulk-invites", args=[event.pk]),
                                     {"emails": [user.email], "send_email": True}, format="json")

    assert response.status_code == 400 and "send_email" in response.data
    assert not event.invites.exists()
    assert not EmailLog.objects.filter(source_kind="event_invitation").exists()
    enqueue.assert_not_called()
    # Binding an email never widens the public discovery surface.
    assert client_for(user).get(public_url(event, "public-event-detail")).status_code == 404


def test_private_event_still_accepts_allowlist_only_invitations(monkeypatch):
    _, actor, user, event, _ = fixture(monkeypatch)
    make_inaccessible(event, "private")
    response = client_for(actor).post(reverse("admin-event-bulk-invites", args=[event.pk]),
                                     {"emails": [user.email], "send_email": False}, format="json")
    assert response.status_code == 201 and response.data == {"created": 1}
    assert event.invites.count() == 1
    assert not EmailLog.objects.filter(source_kind="event_invitation").exists()
    assert client_for(user).get(public_url(event, "public-event-detail")).status_code == 404


@pytest.mark.parametrize("reason", ["private", "draft", "cancelled", "ended"])
def test_queued_invitation_rechecks_navigation_before_smtp(monkeypatch, reason):
    _, actor, user, event, _ = fixture(monkeypatch)
    bulk_invites(event, actor, [user.email])
    log = EmailLog.objects.get(source_kind="event_invitation")
    make_inaccessible(event, reason)
    send = smtp(monkeypatch)

    _deliver(log)

    log.refresh_from_db()
    assert log.status == "skipped" and log.error == "delivery_source_no_longer_eligible"
    send.assert_not_called()
    assert not log.text_body and not log.html_body


def test_public_invitation_mail_links_to_accessible_detail(monkeypatch, settings):
    _, actor, user, event, _ = fixture(monkeypatch)
    bulk_invites(event, actor, [user.email])
    log = EmailLog.objects.get(source_kind="event_invitation")
    send = smtp(monkeypatch)
    message = Mock(wraps=EmailMultiAlternatives)
    monkeypatch.setattr("apps.integrations.dispatch_delivery.EmailMultiAlternatives", message)

    _deliver(log)

    assert log.status == "sent" and send.call_count == 1
    link = f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/m/{event.makerspace.slug}/events/{event.public_token}"
    assert link in message.call_args.kwargs["body"]
    assert client_for(user).get(public_url(event, "public-event-detail")).status_code == 200
