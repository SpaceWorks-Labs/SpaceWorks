"""Creation onboarding issues an email-only staff-role invitation (decisions 63/66: one account per person)."""
import pytest
from django.db import transaction

from apps.accounts.models import StaffInvitation, User
from apps.admin_api.serializers_creation_setup import MakerspaceCreationSetupSerializer
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from .helpers import bearer_client

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("named", [False, True])
def test_creation_invite_creates_no_account_and_delivers_after_commit(monkeypatch, named):
    owner = User.objects.create_superuser("s4b-creation-owner")
    member = User.objects.create_user("s4b-existing-member", email="desk@example.test")
    delivered = []

    def deliver(row, raw):
        assert not transaction.get_connection().in_atomic_block
        assert raw and row.account_id is None
        delivered.append(row.pk)
        return {"delivery_status": "unavailable", "accept_url": "https://example.test/setup#private"}

    monkeypatch.setattr("apps.makerspaces.creation_setup.deliver", deliver)
    invite = {"email": member.email, "role_slug": "space_manager"}
    if named:
        invite["name"] = "Desk operator"
    response = bearer_client(owner, recent=True).post("/api/v1/admin/makerspaces", {
        "organization_name": "S4B owner", "name": "S4B creation", "slug": "s4b-creation",
        "public_code": "S4BC", "location": "Lab", "creation_setup": {
            "modules": ["email"], "first_staff_invite": invite,
        },
    }, format="json")
    assert response.status_code == 201, response.data
    assert "no-store" in response["Cache-Control"]
    space = Makerspace.objects.get(slug="s4b-creation")
    row = StaffInvitation.objects.get(makerspace=space)
    # No account is created and nothing is attached by shared e-mail: the invitee accepts it
    # while signed in to their own account.
    assert row.account_id is None and row.email == member.email
    assert row.role.slug == "space_manager" and row.role_snapshot == ["space_manager"]
    assert row.accepted_at is None and delivered == [row.pk]
    assert not MakerspaceMembership.all_tracks.filter(makerspace=space).exists()
    assert AuditLog.objects.filter(makerspace=space, action="staff_invitation.sent", target_id=str(row.pk)).exists()
    assert not User.objects.filter(email=member.email).exclude(pk=member.pk).exists()
    member.refresh_from_db()
    assert member.account_kind == "member" and not member.makerspace_memberships.exists()


def test_failed_invitation_rolls_back_space_and_audit(monkeypatch):
    from rest_framework.exceptions import ValidationError

    owner = User.objects.create_superuser("s4b-rollback-owner")
    delivered = []

    def refuse(*args, **kwargs):
        assert Makerspace.objects.filter(slug="s4b-rollback").exists()
        raise ValidationError("Onboarding unavailable")

    monkeypatch.setattr("apps.makerspaces.creation_setup.issue_invitation", refuse)
    monkeypatch.setattr("apps.makerspaces.creation_setup.deliver", lambda *args: delivered.append(args))
    response = bearer_client(owner, recent=True).post("/api/v1/admin/makerspaces", {
        "organization_name": "S4B rollback owner", "name": "Rollback", "slug": "s4b-rollback",
        "public_code": "S4BR", "location": "Lab", "creation_setup": {
            "first_staff_invite": {"email": "rollback@example.test", "role_slug": "space_manager"},
        },
    }, format="json")
    assert response.status_code == 400, response.data
    assert not Makerspace.objects.filter(slug="s4b-rollback").exists()
    assert not User.objects.filter(email="rollback@example.test").exists()
    assert not StaffInvitation.objects.exists() and not delivered
    assert not AuditLog.objects.filter(action="staff_invitation.sent").exists()


def test_creation_serializer_documents_the_invitation_and_validates_its_fields():
    serializer = MakerspaceCreationSetupSerializer()
    field = serializer.fields["first_staff_invite"]
    assert "staff-role invitation" in field.help_text
    # Decision 63 (d55545d77): the invite names no new account -- the invitee accepts while signed in
    # to their own -- so there is no display-name field; the address and a staff role are required.
    assert set(field.fields) == {"email", "role_slug"}
    assert field.fields["email"].required and field.fields["role_slug"].required
    assert "member" not in field.fields["role_slug"].choices
    for invite in ({"email": "not-an-address", "role_slug": "space_manager"},
                   {"email": "desk@example.test", "role_slug": "member"},
                   {"email": "desk@example.test"}):
        assert not MakerspaceCreationSetupSerializer(data={"first_staff_invite": invite}).is_valid(), invite
    assert MakerspaceCreationSetupSerializer(data={"first_staff_invite": {
        "email": "desk@example.test", "role_slug": "space_manager"}}).is_valid()
