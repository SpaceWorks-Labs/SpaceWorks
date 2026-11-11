"""Broadcast navigation follows durable participation provenance, without QR secrets."""

from urllib.parse import urlsplit

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events.services_broadcasts import change, compose
from apps.events.services_registration import register
from apps.integrations.broadcasts_worker import broadcast_batch
from apps.integrations.delivery_content import content
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.makerspaces.models import Makerspace
from tests.events.collab_helpers import client_for, collaborate, make_member
from tests.events.lane_d_helpers import fixture, smtp
from tests.events.ticketing_helpers import event_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("provenance", ["host", "partner", "legacy_null"])
def test_sent_ticket_link_resolves_to_the_owners_participation_space(monkeypatch, settings, provenance):
    host, actor, user, event, registration = fixture(monkeypatch)
    ticket_space = host
    if provenance == "partner":
        ticket_space = event_space("broadcast-partner", membership=True)
        collaboration = collaborate(event, ticket_space)
        user = make_member(ticket_space, "broadcast-visitor")
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
        registration = register(event, member=user, actor=user, via_makerspace=ticket_space, collaborative=True)
        # Later collaboration removal must not rewrite participation history.
        collaboration.delete()
    elif provenance == "legacy_null":
        registration.registered_via_makerspace = None
        registration.save(update_fields=["registered_via_makerspace"])
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test/"
    campaign = compose(event, actor, subject="Your ticket", body="{{ ticket_url }}", statuses=["registered"])
    change(campaign, actor, "queue")
    broadcast_batch("event_broadcast", campaign.pk)
    delivery = campaign.deliveries.get(recipient=user)
    log = EmailLog.objects.get(pk=delivery.outbox_id)
    send = smtp(monkeypatch)
    _deliver(log)
    assert log.status == "sent" and send.call_count == 1
    url = content(log).text_body.strip()
    assert url == f"https://app.example.test/m/{ticket_space.slug}/member/events/{registration.pk}/ticket"
    assert str(registration.checkin_token) not in url
    # Match the SPA: resolve the URL's slug, then call the scoped ticket API.
    linked_space = Makerspace.objects.get(slug=urlsplit(url).path.split("/")[2])
    path = reverse("member-event-ticket", args=[linked_space.pk, registration.pk])
    response = client_for(user).get(path)
    assert response.status_code == 200, response.data
    assert response.data["registration_id"] == registration.pk
    assert client_for(actor).get(path).status_code in {403, 404}
