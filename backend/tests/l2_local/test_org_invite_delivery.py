"""Decision #145: organisation invites may name an invitee email -- digest only, email + chat."""
import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.organizations import invitation_delivery
from apps.organizations.models import OrganizationInvitation, OrganizationMakerspace, OrganizationMembership
from apps.organizations.services_invitations import create_invitation
from tests.events.ticketing_helpers import account, event_space
from tests.organizations.test_org_authority import make_organization, make_user

pytestmark = pytest.mark.django_db


def org_admin():
    organization = make_organization("invite-org")
    admin = make_user("invite-admin")
    OrganizationMembership.objects.create(organization=organization, user=admin,
                                          governance_actions=["manage_organization_members"])
    return organization, admin


def test_without_an_email_nothing_is_sent_and_nothing_is_stored(django_capture_on_commit_callbacks):
    organization, admin = org_admin()
    with django_capture_on_commit_callbacks(execute=True):
        invitation, _token = create_invitation(organization, actor=admin, governance_actions=[], granted_actions=[])
    assert invitation.invitee_email_digest == ""
    assert not AuditLog.objects.filter(action="organization.invitation_delivered").exists()


def test_email_is_digested_sent_and_chat_offered_to_a_verified_account(django_capture_on_commit_callbacks, monkeypatch):
    organization, admin = org_admin()
    space = event_space("invite-org-space")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=space, relationship="owner")
    person = account("org-invitee")
    person.email_verified_at = timezone.now()
    person.save(update_fields=["email_verified_at"])
    sent = []
    monkeypatch.setattr("apps.integrations.dispatch.dispatch_email", lambda **kwargs: sent.append(kwargs))
    with django_capture_on_commit_callbacks(execute=True):
        invitation, token = create_invitation(organization, actor=admin, governance_actions=[], granted_actions=[],
                                              invitee_email="org-invitee@example.test")
    stored = OrganizationInvitation.objects.get(pk=invitation.pk)
    assert stored.invitee_email_digest == invitation_delivery.email_digest("ORG-INVITEE@example.test")
    assert "org-invitee" not in stored.invitee_email_digest
    assert sent and sent[0]["to_email"] == "org-invitee@example.test" and token in sent[0]["text_body"]
    envelope = NotificationEnvelope.objects.get(source_kind="integrations.invitation", recipient=person)
    assert envelope.makerspace_id == space.pk
    from apps.integrations.invite_chat import invite_eligible
    assert invite_eligible(envelope)
    OrganizationInvitation.objects.filter(pk=invitation.pk).update(revoked_at=timezone.now())
    assert not invite_eligible(envelope)
    audit = AuditLog.objects.get(action="organization.invitation_delivered")
    assert audit.meta["chat_offered"] is True and "email" not in str(audit.meta).replace("emailed", "")


def test_api_accepts_the_optional_email_and_reports_it_was_sent(monkeypatch):
    from rest_framework.test import APIClient
    organization, admin = org_admin()
    monkeypatch.setattr("apps.accounts.reauthentication.require_recent_reauth", lambda request: None)
    monkeypatch.setattr("apps.organizations.invitation_delivery.send", lambda *args: (True, False))
    client = APIClient()
    client.force_authenticate(admin)
    response = client.post(f"/api/v1/admin/organizations/{organization.pk}/invitations/",
                           {"invitee_email": "someone@example.test"}, format="json")
    assert response.status_code == 201 and response.json()["sent_to_email"] is True
