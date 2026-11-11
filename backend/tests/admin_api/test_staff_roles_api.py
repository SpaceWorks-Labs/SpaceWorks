"""U-B: makerspaces/<id>/staff-roles/ — staff roles on people (local test, never committed)."""

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.mfa_policy import credential, stamp
from apps.accounts.models import StaffInvitation, User
from apps.accounts.models_devices import DeviceGrant
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.reauthentication import versions
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.accounts.account_factories import device_grant, grant_staff_role, make_membership, make_staff
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db
PASSWORD = "Staff roles password 19!"
ORIGIN = "http://localhost:5000"


@pytest.fixture(autouse=True)
def keys(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.PLATFORM_STAFF_ORIGINS = [ORIGIN]
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]


@pytest.fixture
def space():
    row = Makerspace.objects.create(name="Roles A", slug="roles-a")
    row.enabled_modules = sorted({*(row.enabled_modules or []), "email"})
    row.save(update_fields=["enabled_modules"])
    return row


def client_for(user):
    if not user.is_superuser:
        enrolled(user)
        stamp(user, credential(user), "totp")
    token = SpaceWorksRefreshToken.for_user(user).access_token
    ReauthenticationSession.objects.update_or_create(session_id=token["sid"], defaults={
        "user": user, "surface": token["surface"], "auth_time": timezone.now(), **versions(user)})
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_ORIGIN=ORIGIN)
    return api


def url(space, row=None, action=""):
    base = f"/api/v1/admin/makerspaces/{space.pk}/staff-roles/"
    return base if row is None else f"{base}{row.pk}/{action + '/' if action else ''}"


def member(space, username):
    user = User.objects.create_user(username=username, password=PASSWORD, email=f"{username}@example.com")
    make_membership(user, space)
    return user


def row_of(user, space):
    return MakerspaceMembership.staff_tracks.get(user=user, makerspace=space)


def test_list_carries_rows_and_policy(space):
    manager = make_staff(space, username="sr-manager", password=PASSWORD)
    make_staff(space, username="sr-tech", password=PASSWORD, role_slug="inventory_manager")
    response = client_for(manager).get(url(space))
    assert response.status_code == 200, response.data
    assert {row["username"] for row in response.data["results"]} == {"sr-manager", "sr-tech"}
    policy = response.data["policy"]
    assert policy["can_manage_space_managers"] is False
    assert "space_manager" not in {role["slug"] for role in policy["grantable_roles"]}
    assert policy["email_invites_available"] is True
    assert response["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("actor_kind", ["manager", "platform"])
def test_policy_machine_picker_includes_local_and_builtin_but_not_foreign_types(space, actor_kind):
    from apps.machines.models import MachineType

    other = Makerspace.objects.create(name="Picker other", slug="picker-other")
    local = MachineType.objects.create(makerspace=space, slug="picker-local", name="Picker local")
    builtin = MachineType.objects.create(is_builtin=True, slug="picker-builtin", name="Picker builtin")
    foreign = MachineType.objects.create(makerspace=other, slug="picker-foreign", name="Picker foreign")
    if actor_kind == "platform":
        actor = User.objects.create_superuser("sr-picker-root", password=PASSWORD)
    else:
        actor = make_staff(space, username="sr-picker-manager", password=PASSWORD)

    response = client_for(actor).get(url(space))

    assert response.status_code == 200, response.data
    choices = response.data["policy"]["machine_types"]
    ids = {row["id"] for row in choices}
    assert {local.pk, builtin.pk} <= ids
    assert foreign.pk not in ids
    assert all(set(row) == {"id", "name"} for row in choices)
    assert response["Cache-Control"] == "private, no-store"


def test_grant_only_to_a_community_member(space):
    manager = make_staff(space, username="sr-m2", password=PASSWORD)
    api = client_for(manager)
    outsider = User.objects.create_user(username="sr-outsider", password=PASSWORD)
    refused = api.post(url(space), {"user_id": outsider.pk, "roles": ["inventory_manager"]}, format="json")
    assert refused.status_code == 409 and refused.data["code"] == "not_community_member"
    person = member(space, "sr-member")
    granted = api.post(url(space), {"user_id": person.pk, "roles": ["inventory_manager"]}, format="json")
    assert granted.status_code == 201, granted.data
    assert granted.data["kind"] == "granted" and granted.data["staff_role"]["roles"] == ["inventory_manager"]
    assert row_of(person, space).status == "active"
    assert AuditLog.objects.filter(action="staff_role.granted", makerspace=space).exists()
    again = api.post(url(space), {"user_id": person.pk, "roles": ["event_manager"]}, format="json")
    assert again.status_code == 409 and again.data["code"] == "already_staff"


def test_invite_by_email_never_returns_the_link(space):
    manager = make_staff(space, username="sr-m3", password=PASSWORD)
    response = client_for(manager).post(url(space), {"email": "New.Person@Example.com", "roles": ["event_manager"]},
                                        format="json")
    assert response.status_code == 201, response.data
    assert response.data["kind"] == "invited" and "accept_url" not in str(response.data)
    invitation = StaffInvitation.objects.get(pk=response.data["invitation_id"])
    assert invitation.account_id is None and invitation.email == "new.person@example.com"
    assert invitation.role_snapshot == ["event_manager"]
    assert AuditLog.objects.filter(action="staff_invitation.sent").exists()
    listed = client_for(manager).get(f"/api/v1/admin/makerspaces/{space.pk}/staff-invitations")
    assert listed.status_code == 200 and "accept_url" not in str(listed.data)


def test_patch_roles_and_machine_scopes(space):
    from apps.machines.models import MachineType
    manager = make_staff(space, username="sr-m4", password=PASSWORD)
    tech = make_staff(space, username="sr-mm", password=PASSWORD, role_slug="inventory_manager")
    kind = MachineType.objects.create(makerspace=space, name="Laser", slug="laser")
    api = client_for(manager)
    changed = api.patch(url(space, row_of(tech, space)), {"roles": ["machine_manager"], "machine_type_ids": [kind.pk]},
                        format="json")
    assert changed.status_code == 200, changed.data
    assert changed.data["roles"] == ["machine_manager"] and changed.data["machine_type_ids"] == [kind.pk]
    assert AuditLog.objects.filter(action="staff_role.changed").exists()
    bad = api.patch(url(space, row_of(tech, space)), {"roles": ["inventory_manager"], "machine_type_ids": [kind.pk]},
                    format="json")
    assert bad.status_code == 400


def test_revoke_and_restore_keep_member_features_and_revoke_staff_grants(space):
    manager = make_staff(space, username="sr-m5", password=PASSWORD)
    tech = make_staff(space, username="sr-t5", password=PASSWORD, role_slug="inventory_manager")
    grant = device_grant(tech, staff_makerspace_id=space.pk)
    api = client_for(manager)
    revoked = api.post(url(space, row_of(tech, space), "revoke"), {"reason": "Left the team"}, format="json")
    assert revoked.status_code == 200, revoked.data
    assert revoked.data["status"] == "revoked"
    grant.refresh_from_db()
    assert grant.status != DeviceGrant.Status.ACTIVE or grant.revoked_at is not None
    tech.refresh_from_db()
    assert tech.is_active
    restored = api.post(url(space, row_of(tech, space), "restore"), format="json")
    assert restored.status_code == 200 and restored.data["status"] == "active"
    assert {"staff_role.revoked", "staff_role.restored"} <= set(AuditLog.objects.values_list("action", flat=True))


def test_no_self_change(space):
    manager = make_staff(space, username="sr-self", password=PASSWORD)
    response = client_for(manager).post(url(space, row_of(manager, space), "revoke"), {}, format="json")
    assert response.status_code == 403 and response.data["code"] == "self_change"


def test_space_manager_role_is_superadmin_only(space):
    manager = make_staff(space, username="sr-m6", password=PASSWORD)
    other_manager = make_staff(space, username="sr-other-sm", password=PASSWORD)
    person = member(space, "sr-promote")
    api = client_for(manager)
    grant = api.post(url(space), {"user_id": person.pk, "roles": ["space_manager"]}, format="json")
    assert grant.status_code == 403 and grant.data["code"] == "space_manager_superadmin_only"
    revoke = api.post(url(space, row_of(other_manager, space), "revoke"), {}, format="json")
    assert revoke.status_code == 403 and revoke.data["code"] == "space_manager_superadmin_only"
    root = User.objects.create_superuser("sr-root", password=PASSWORD)
    root_api = client_for(root)
    listed = root_api.get(url(space))
    assert listed.status_code == 200, listed.data
    assert listed.data["policy"]["can_manage_space_managers"] is True
    promoted = root_api.post(url(space), {"user_id": person.pk, "roles": ["space_manager"]}, format="json")
    assert promoted.status_code == 201, promoted.data
    demoted = root_api.post(url(space, row_of(other_manager, space), "revoke"), {}, format="json")
    assert demoted.status_code == 200, demoted.data


def test_last_manager_is_kept(space):
    manager = make_staff(space, username="sr-last", password=PASSWORD)
    root = User.objects.create_superuser("sr-root-2", password=PASSWORD)
    response = client_for(root).post(url(space, row_of(manager, space), "revoke"), {}, format="json")
    assert response.status_code == 409 and response.data["code"] == "last_manager"


def test_quota_refuses_with_a_code(space, monkeypatch):
    from apps.makerspaces import limits
    manager = make_staff(space, username="sr-quota", password=PASSWORD)
    person = member(space, "sr-q-member")
    monkeypatch.setattr(limits, "resource_limit", lambda makerspace, key: 0 if key == "staff" else None)
    response = client_for(manager).post(url(space), {"user_id": person.pk, "roles": ["inventory_manager"]},
                                        format="json")
    assert response.status_code == 409 and response.data["code"] == "quota_exceeded"


def test_tenant_gate_refuses_with_a_code(space):
    from apps.tenant_migration.models_source_gate import SourceMigrationGate
    manager = make_staff(space, username="sr-gate", password=PASSWORD)
    person = member(space, "sr-g-member")
    api = client_for(manager)
    import uuid
    from datetime import timedelta
    now = timezone.now()
    SourceMigrationGate.objects.create(makerspace=space, state="quiesced", owner_id=uuid.uuid4(),
                                       heartbeat_at=now, lease_expires_at=now + timedelta(hours=1))
    response = api.post(url(space), {"user_id": person.pk, "roles": ["inventory_manager"]}, format="json")
    assert response.status_code == 423  # the request gate answers first over HTTP
    from apps.accounts import staff_account_services as service
    from apps.accounts.staff_account_policy import StaffRoleRefused
    with pytest.raises(StaffRoleRefused) as refused:  # the service refuses on its own with the typed code
        service.grant(manager, space.pk, user_id=person.pk, roles=["inventory_manager"])
    assert refused.value.detail["code"] == "tenant_gated"


def test_old_staff_account_routes_are_gone(space):
    manager = make_staff(space, username="sr-gone", password=PASSWORD)
    response = client_for(manager).get(f"/api/v1/admin/makerspaces/{space.pk}/staff-accounts/")
    assert response.status_code == 404


def test_other_space_manager_cannot_reach(space):
    other = Makerspace.objects.create(name="Roles B", slug="roles-b")
    outsider = make_staff(other, username="sr-b-manager", password=PASSWORD)
    response = client_for(outsider).get(url(space))
    assert response.status_code in {403, 404}


def test_superadmin_sees_masked_staff_without_a_pii_window(space):
    make_staff(space, username="sr-masked", password=PASSWORD, email="masked@example.com", display_name="Masked Person")
    root = User.objects.create_superuser("sr-root-3", password=PASSWORD)
    response = client_for(root).get(url(space))
    assert response.status_code == 200, response.data
    row = response.data["results"][0]
    assert row["email"] != "masked@example.com" and row.get("pii_masked") is True
    assert grant_staff_role  # imported for other files' parity
