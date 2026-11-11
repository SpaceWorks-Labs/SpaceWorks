"""Creation onboarding creates a tenant principal before its account-bound invite."""
import pytest
from django.db import transaction

from apps.accounts.models import StaffInvitation, User
from apps.admin_api.serializers_creation_setup import MakerspaceCreationSetupSerializer
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from .helpers import bearer_client

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("named", [False, True])
def test_creation_invite_is_separate_from_same_email_member_and_delivers_after_commit(monkeypatch, named):
    owner = User.objects.create_superuser("s4b-creation-owner")
    member = User.objects.create_user("s4b-existing-member", email="desk@example.test")
    delivered = []

    def deliver(row, raw):
        assert not transaction.get_connection().in_atomic_block
        assert row.account.account_kind == "staff" and raw
        assert row.account.staff_makerspace_id == row.makerspace_id
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
    account = row.account
    assert account.pk != member.pk and account.email == member.email
    assert account.display_name == ("Desk operator" if named else "desk")
    assert not account.has_usable_password() and account.must_change_password
    membership = MakerspaceMembership.objects.get(user=account)
    assert membership.makerspace_id == space.pk and membership.assigned_role.slug == "space_manager"
    assert row.role_snapshot == ["space_manager"] and row.credential_generation == account.credential_generation
    assert delivered == [row.pk]
    assert AuditLog.objects.filter(makerspace=space, action="staff.account_created", target_id=str(account.pk)).exists()
    member.refresh_from_db()
    assert member.account_kind == "member" and not member.makerspace_memberships.exists()


def test_failed_invitation_rolls_back_space_account_membership_and_audit(monkeypatch):
    from rest_framework.exceptions import ValidationError

    owner = User.objects.create_superuser("s4b-rollback-owner")
    delivered = []

    def refuse(*args, **kwargs):
        assert User.objects.filter(account_kind="staff", email="rollback@example.test").exists()
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
    assert not AuditLog.objects.filter(action="staff.account_created").exists()


def test_creation_serializer_documents_account_creation_and_validates_name():
    serializer = MakerspaceCreationSetupSerializer()
    field = serializer.fields["first_staff_invite"]
    assert "separate staff account" in field.help_text
    assert "name" in field.fields and not field.fields["name"].required
    invalid = MakerspaceCreationSetupSerializer(data={"first_staff_invite": {
        "name": " " * 3, "email": "desk@example.test", "role_slug": "space_manager",
    }})
    assert not invalid.is_valid()
