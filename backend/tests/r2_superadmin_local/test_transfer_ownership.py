"""#185 item 3: transfer ownership through the staff-role services, audited."""

import pytest

from apps.accounts.models import StaffInvitation, User
from apps.accounts.staff_account_policy import role_keys
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership

from .helpers import api, control, manager, member, space, superadmin

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(mailbox):
    lab = space()
    root, old, newcomer = superadmin(), manager(lab, "old-manager"), member(lab, "new-manager")
    old_row = MakerspaceMembership.staff_tracks.get(makerspace=lab, user=old)
    return type("World", (), dict(lab=lab, root=root, old=old, old_row=old_row, newcomer=newcomer))


def transfer(world, **body):
    return control(world.root, world.lab, "transfer-ownership", body)


def staff_row(world, user):
    return MakerspaceMembership.staff_tracks.filter(makerspace=world.lab, user=user).first()


def test_member_becomes_manager_and_old_manager_keeps_chosen_roles(world):
    response = transfer(world, email=world.newcomer.email, previous_membership_id=world.old_row.pk,
                        previous_outcome="keep_staff", previous_roles=["inventory_manager"])
    assert response.status_code == 200, response.content
    assert response.json()["status"] == "transferred"
    assert role_keys(staff_row(world, world.newcomer)) == ["space_manager"]
    assert role_keys(staff_row(world, world.old)) == ["inventory_manager"]
    entry = AuditLog.objects.get(action="space_control.ownership_transferred")
    assert entry.meta == {"new_user_id": world.newcomer.pk, "previous_user_id": world.old.pk,
                          "previous_outcome": "keep_staff"}
    assert [m["user_id"] for m in response.json()["card"]["managers"]] == [world.newcomer.pk]


def test_old_manager_can_be_revoked(world):
    assert transfer(world, email=world.newcomer.email, previous_membership_id=world.old_row.pk,
                    previous_outcome="revoke").status_code == 200
    assert staff_row(world, world.old).status == "revoked"
    assert staff_row(world, world.newcomer).status == "active"


def test_old_manager_can_stay_as_co_manager(world):
    assert transfer(world, email=world.newcomer.email, previous_membership_id=world.old_row.pk,
                    previous_outcome="keep_manager").status_code == 200
    assert role_keys(staff_row(world, world.old)) == ["space_manager"]


def test_unknown_email_gets_an_invitation_and_the_old_manager_is_untouched(world):
    response = transfer(world, email="fresh@example.test", previous_membership_id=world.old_row.pk,
                        previous_outcome="revoke")
    assert response.status_code == 200 and response.json()["status"] == "invited"
    invitation = StaffInvitation.objects.get(makerspace=world.lab)
    assert invitation.role_snapshot == ["space_manager"] and invitation.email == "fresh@example.test"
    assert staff_row(world, world.old).status == "active"
    assert AuditLog.objects.filter(action="space_control.ownership_invited").exists()


def test_refusals(world):
    assert transfer(world, email=world.old.email, previous_membership_id=world.old_row.pk,
                    previous_outcome="revoke").status_code == 400
    assert transfer(world, email=world.newcomer.email, previous_outcome="keep_staff",
                    previous_membership_id=world.old_row.pk, previous_roles=[]).status_code == 400
    assert transfer(world, email=world.newcomer.email, previous_membership_id=999999,
                    previous_outcome="revoke").status_code == 400
    assert api(world.old).post(f"/api/v1/admin/platform/spaces/{world.lab.pk}/transfer-ownership",
                               {"email": world.newcomer.email}, format="json").status_code == 403
    assert not User.objects.filter(email="fresh@example.test").exists()
