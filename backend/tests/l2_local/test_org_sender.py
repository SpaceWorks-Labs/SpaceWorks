"""X2 + #115a: co-host sender name and Reply-To, never the From address; superadmin can edit."""
from types import SimpleNamespace

import pytest
from django.core.mail import EmailMultiAlternatives
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.organizer_models import EventOrganizer
from apps.integrations import org_sender
from apps.integrations.models_org_sender import OrganizationEmailSender
from apps.organizations.models import OrganizationMembership
from tests.events.ticketing_helpers import event_space, open_event
from tests.l2_local.helpers import off, on
from tests.organizations.test_org_authority import make_organization, make_user

pytestmark = pytest.mark.django_db


def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def test_org_admin_and_superadmin_edit_and_every_change_is_audited():
    org = make_organization("sender-org")
    admin = make_user("sender-admin")
    OrganizationMembership.objects.create(organization=org, user=admin,
                                          governance_actions=["manage_organization_profile"])
    url = f"/api/v1/admin/organizations/{org.pk}/email-sender/"
    response = client(admin).put(url, {"sender_name": "Robotics Club", "reply_to": "hello@club.example"},
                                 format="json")
    assert response.status_code == 200 and response.json()["sender_name"] == "Robotics Club"
    outsider = make_user("sender-outsider")
    assert client(outsider).get(url).status_code in (403, 404)
    superadmin = make_user("sender-root", is_superuser=True, account_kind="platform")
    assert client(superadmin).put(url, {"sender_name": "Club", "reply_to": ""}, format="json").status_code == 200
    assert AuditLog.objects.filter(action="organization.email_sender_updated").count() == 2


def test_event_email_shows_the_co_host_name_only_while_the_switch_is_on(monkeypatch):
    space = event_space("sender-space")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"email", "notifications"})
    space.save(update_fields=["enabled_modules"])
    event = open_event(space)
    org = make_organization("cohost-org")
    EventOrganizer.objects.create(event=event, organization=org)
    OrganizationEmailSender.objects.create(organization=org, sender_name="Cohost", reply_to="cohost@example.test")
    monkeypatch.setattr(org_sender, "_event_id_for", lambda log: event.pk)
    log = SimpleNamespace(pk=1, makerspace=space, makerspace_id=space.pk)
    msg = EmailMultiAlternatives(subject="s", body="b", from_email="Space <space@example.test>", to=["a@b.c"])
    off(space, "events.organization_sender")
    org_sender.apply(log, msg)
    assert msg.from_email == "Space <space@example.test>" and not msg.reply_to
    on(space, "events.organization_sender")
    org_sender.apply(log, msg)
    assert msg.from_email.endswith("<space@example.test>") and "Cohost via" in msg.from_email
    assert msg.reply_to == ["cohost@example.test"]
