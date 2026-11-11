"""Consumption credits the initiator while email binding still checks the participant."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events import services
from apps.events.invites import create_invite
from tests.events.collab_helpers import client_for
from tests.events.organization_audience_helpers import audience_fixture, direct
from tests.events.ticketing_helpers import signup

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("path", ["automatic_email", "organization_code", "invite_code"])
@pytest.mark.parametrize("initiator", ["staff", "self"])
@pytest.mark.parametrize("reuse_cancelled", [False, True])
def test_invite_consumption_uses_initiating_actor(path, initiator, reuse_cancelled):
    _, orgs, _, event, manager = audience_fixture()
    if path == "invite_code":
        event.registration_audience = "invite"
        event.save(update_fields=["registration_audience"])
    user = direct(orgs[0])
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    actor = manager if initiator == "staff" else user
    url = reverse("admin-event-registration-list", args=[event.pk])

    def register(code):
        payload = {"invite_code": code} if path != "automatic_email" else {}
        if initiator == "staff":
            return client_for(manager).post(url, {"member_id": user.pk, **payload}, format="json")
        return signup(event, user, **payload)

    if reuse_cancelled:
        _, old_code = create_invite(event, actor=manager, email=user.email)
        assert register(old_code).status_code == 201
        # A member's own cancellation goes through the member path; staff need the permission.
        services.cancel_registration(event.registrations.get(), actor=actor, member_cancel=actor == user)
    invite, code = create_invite(event, actor=manager, email=user.email)
    response = register(code)
    assert response.status_code == 201, response.data
    row = event.registrations.get()
    assert row.member_id == user.pk and row.invite_id == invite.pk
    invite.refresh_from_db()
    assert invite.uses == 1
    consumed = AuditLog.objects.get(action="event.invite_consumed", target_id=str(invite.pk))
    assert consumed.actor_id == actor.pk and consumed.meta == {"uses": 1}
    created = AuditLog.objects.filter(action="event.registration_created", target_id=str(row.pk)).latest("id")
    redeemed = AuditLog.objects.filter(action="event.invite_redeemed", target_id=str(row.pk)).latest("id")
    assert created.actor_id == redeemed.actor_id == actor.pk
    if initiator == "self":
        assert register(code).status_code == 201
        invite.refresh_from_db()
        assert invite.uses == 1
        assert AuditLog.objects.filter(action="event.invite_consumed", target_id=str(invite.pk)).count() == 1
