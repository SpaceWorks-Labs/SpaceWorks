"""Closed private partner events expose owned consent repair without new admission."""

import pytest
from django.urls import reverse

from apps.events.models import EventRegistration
from apps.makerspaces.waiver_services import publish_waiver
from tests.events.collab_helpers import client_for
from tests.events.organization_audience_helpers import local
from tests.events.test_waiver_consent_repair_cutoff import consent, queued_fixture, unchanged_fields

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("operation", ["approve", "manual", "automatic"])
def test_closed_private_partner_list_exposes_consent_then_repairs_without_readmission(operation):
    venue, event, manager, user, row, waiver, partner = queued_fixture(operation, "partner")
    event.is_public = False
    event.save(update_fields=["is_public"])
    client = client_for(user)
    listing = reverse("member-collaborative-events", args=[partner.pk])
    signup = reverse("member-collaborative-event-register", args=[partner.pk, event.pk])
    before = unchanged_fields(row)
    response = client.get(listing)
    assert response.status_code == 200, response.data
    assert response["Cache-Control"] == "private, no-store"
    item = next(item for item in response.data if item["id"] == event.pk)
    assert item["registration_open"] is False
    assert item["consent_repair_required"] is True
    assert item["host_waiver"] == {"id": waiver.pk, "version": "v2", "body": waiver.body}
    response = client.post(signup, consent(waiver), format="json")
    assert response.status_code == 201, response.data
    row.refresh_from_db()
    assert unchanged_fields(row) == before
    assert row.host_waiver_id == waiver.pk
    assert next(item for item in client.get(listing).data if item["id"] == event.pk)["consent_repair_required"] is False
    # A later publication must make the advisory stale again, even with signup closed.
    publish_waiver(manager, venue, "Third terms", "v3")
    assert next(item for item in client.get(listing).data if item["id"] == event.pk)["consent_repair_required"] is True


@pytest.mark.parametrize("state", ["new", "cancelled", "rejected", "attended"])
def test_partner_repair_is_owned_and_live_only_and_does_not_reopen_signup(state):
    _, event, _, user, row, waiver, partner = queued_fixture(route="partner")
    event.is_public = False
    event.save(update_fields=["is_public"])
    if state == "new":
        user = local(partner, "another-partner")
    else:
        row.status = state
        row.save(update_fields=["status"])
    client = client_for(user)
    response = client.get(reverse("member-collaborative-events", args=[partner.pk]))
    assert response.status_code == 200, response.data
    assert next(item for item in response.data if item["id"] == event.pk)["consent_repair_required"] is False
    count = EventRegistration.objects.count()
    response = client.post(reverse("member-collaborative-event-register", args=[partner.pk, event.pk]),
                           {**consent(waiver), "custom_answers": {"reason": "attempt"}}, format="json")
    assert response.status_code == 409, response.data
    row.refresh_from_db()
    assert row.host_waiver_version_accepted == "v1"
    assert EventRegistration.objects.count() == count
