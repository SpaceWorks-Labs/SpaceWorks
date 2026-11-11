"""L6 G32: transfers rotate the credential and move the registration to the new account."""

import secrets

import pytest
from django.urls import reverse

from apps.events.models import EventTicketTransfer
from apps.events.orders_attendees import token_digest
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import place, settings_for, ticketed_event, verified

pytestmark = pytest.mark.django_db


def _offer(user, registration, email):
    return client_for(user).post(reverse("member-ticket-transfer", kwargs={
        "makerspace_id": registration.event.makerspace_id, "pk": registration.pk}), {"email": email}, format="json")


def _registered(django_capture_on_commit_callbacks):
    space, event, _staff, ticket = ticketed_event(amount=0)
    owner = verified("owner")
    with django_capture_on_commit_callbacks(execute=True):
        place(owner, event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    return event, owner, owner.event_registrations.get()


def test_transfer_needs_the_organiser_switch(django_capture_on_commit_callbacks):
    event, owner, registration = _registered(django_capture_on_commit_callbacks)
    refused = _offer(owner, registration, "friend@example.test")
    assert refused.status_code == 409 and refused.data["code"] == "transfer_not_allowed"


def test_accepted_transfer_moves_registration_and_rotates_token(django_capture_on_commit_callbacks):
    event, owner, registration = _registered(django_capture_on_commit_callbacks)
    settings_for(event, transfers_allowed=True)
    friend = verified("friend")
    with django_capture_on_commit_callbacks(execute=True):
        assert _offer(owner, registration, friend.email).status_code == 201
    transfer = EventTicketTransfer.objects.get()
    token = secrets.token_urlsafe(16)
    EventTicketTransfer.objects.filter(pk=transfer.pk).update(token_digest=token_digest(token))
    old_token = registration.checkin_token
    url = reverse("member-ticket-transfer-accept", kwargs={"token": token})
    assert client_for(verified("stranger")).post(url).data["code"] == "claim_email_mismatch"
    with django_capture_on_commit_callbacks(execute=True):
        accepted = client_for(friend).post(url)
    assert accepted.status_code == 201, accepted.data
    registration.refresh_from_db()
    assert registration.member == friend and registration.email == friend.email
    if registration.credential_mode == "legacy":
        assert registration.checkin_token != old_token
    transfer.refresh_from_db()
    assert transfer.status == "accepted"
    assert client_for(friend).post(url).status_code == 404
