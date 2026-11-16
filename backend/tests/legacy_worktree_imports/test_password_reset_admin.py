import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db


def make_superadmin(username):
    return make_user(
        username,
        role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
    )


def reset_password_url(user):
    return reverse("admin-user-reset-password", kwargs={"pk": user.id})


@pytest.mark.skip(reason="U-A1/U-B: the /admin/makerspaces/<id>/staff-accounts/ set-password route is retired (404); a staff-track holder is a person on one account, reset through the person path")
def test_makerspace_admin_resets_managed_staff():
    space = make_space("admin-reset-managed")
    admin = make_member("admin-reset-manager", space)
    target = make_member(
        "admin-reset-inventory",
        space,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER,
        role=User.Role.REQUESTER,
    )
    client = authenticated_client(admin)

    first = client.post(f"/api/v1/admin/makerspaces/{space.pk}/staff-accounts/{target.pk}/set-password/", {"generate": True}, format="json")
    target.refresh_from_db()
    second = client.post(f"/api/v1/admin/makerspaces/{space.pk}/staff-accounts/{target.pk}/set-password/", {"generate": True}, format="json")
    target.refresh_from_db()

    assert first.status_code == 200
    assert first.data["generated_password"]
    assert target.must_change_password is True
    assert second.status_code == 200
    assert second.data["generated_password"]


def test_cannot_reset_superadmin_target():
    space = make_space("admin-reset-super-target")
    actor = make_member("admin-reset-super-actor", space)
    target = make_superadmin("admin-reset-super-target")

    response = authenticated_client(actor).post(reset_password_url(target), {}, format="json")

    # 404-before-403: a superadmin target is outside a makerspace admin's scope, so it
    # is "not found" rather than "forbidden" — no probing for user existence by id.
    assert response.status_code == 404


@pytest.mark.skip(reason="decision 110 (superadmin always on; hidden-tenant reset refusal and Makerspace.superadmin_access_enabled removed)")
def test_platform_cannot_reset_hidden_tenant_staff_even_for_recovery():
    hidden_space = make_space("admin-reset-hidden")
    hidden_space.superadmin_access_enabled = False
    hidden_space.save(update_fields=["superadmin_access_enabled"])
    target = make_member("admin-reset-hidden-manager", hidden_space)
    superadmin = make_superadmin("admin-reset-hidden-super")
    old_password = target.password
    response = authenticated_client(superadmin).post(reset_password_url(target), {}, format="json")
    assert response.status_code == 403
    assert "temporary_password" not in response.data
    target.refresh_from_db()
    assert target.password == old_password
    assert target.must_change_password is False


@pytest.mark.skip(reason="decision 110 (superadmin always on; hidden-tenant reset refusal and Makerspace.superadmin_access_enabled removed)")
def test_an_enabled_tenant_staff_account_does_not_grant_access_to_the_hidden_account():
    hidden_space = make_space("admin-reset-mixed-hidden")
    hidden_space.superadmin_access_enabled = False
    hidden_space.save(update_fields=["superadmin_access_enabled"])
    enabled_space = make_space("admin-reset-mixed-enabled")
    target = make_member("admin-reset-mixed-manager", hidden_space)
    other = make_member("admin-reset-mixed-manager-enabled", enabled_space)
    assert target.pk != other.pk
    old_password = target.password
    response = authenticated_client(make_superadmin("admin-reset-mixed-super")).post(
        reset_password_url(target), {}, format="json")
    assert response.status_code == 403
    assert "temporary_password" not in response.data
    target.refresh_from_db()
    assert target.password == old_password


@pytest.mark.skip(reason="decision 110 (superadmin always on; hidden-tenant reset refusal and Makerspace.superadmin_access_enabled removed)")
def test_superadmin_cannot_reset_hidden_non_space_manager():
    hidden_space = make_space("admin-reset-hidden-inventory")
    make_member("admin-reset-hidden-inventory-manager", hidden_space)
    hidden_space.superadmin_access_enabled = False
    hidden_space.save(update_fields=["superadmin_access_enabled"])
    target = make_member(
        "admin-reset-hidden-inventory-target",
        hidden_space,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER,
        role=User.Role.REQUESTER,
    )
    superadmin = make_superadmin("admin-reset-hidden-inventory-super")

    response = authenticated_client(superadmin).post(
        reset_password_url(target),
        {},
        format="json",
    )

    assert response.status_code == 403
    target.refresh_from_db()
    assert target.must_change_password is False


def test_non_superadmin_cannot_reset_peer_space_manager():
    space = make_space("admin-reset-peer")
    actor = make_member("admin-reset-peer-actor", space)
    target = make_member("admin-reset-peer-target", space)

    response = authenticated_client(actor).post(reset_password_url(target), {}, format="json")

    # Peer Space Manager in the SAME space: target is in scope (found), then blocked 403.
    assert response.status_code == 403


def test_non_superadmin_cannot_reset_user_outside_scope():
    space_a = make_space("admin-reset-scope-a")
    space_b = make_space("admin-reset-scope-b")
    actor = make_member("admin-reset-scope-actor", space_a)
    target = make_member(
        "admin-reset-scope-target",
        space_b,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER,
        role=User.Role.REQUESTER,
    )

    response = authenticated_client(actor).post(reset_password_url(target), {}, format="json")

    # Target lives only in space B, outside the actor's authority → 404, not a 403 that
    # would confirm the user id exists.
    assert response.status_code == 404


@pytest.mark.skip(reason="U-A1/U-B: the /admin/makerspaces/<id>/staff-accounts/ set-password route is retired (404); a staff-track holder is a person on one account, reset through the person path")
def test_admin_reset_blacklists_outstanding_tokens():
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )
    from apps.accounts.tokens import SpaceWorksRefreshToken

    space = make_space("admin-reset-revoke")
    admin = make_member("admin-reset-revoke-actor", space)
    target = make_member(
        "admin-reset-revoke-target",
        space,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER,
        role=User.Role.REQUESTER,
    )
    # A live session for the target: its refresh token is recorded as outstanding.
    SpaceWorksRefreshToken.for_user(target)
    outstanding = OutstandingToken.objects.filter(user=target)
    assert outstanding.exists()
    assert not BlacklistedToken.objects.filter(token__in=outstanding).exists()

    response = authenticated_client(admin).post(
        f"/api/v1/admin/makerspaces/{space.pk}/staff-accounts/{target.pk}/set-password/",
        {"generate": True}, format="json")

    assert response.status_code == 200
    # Every pre-reset refresh token is now blacklisted, so the old session can't refresh.
    assert BlacklistedToken.objects.filter(token__in=outstanding).count() == outstanding.count()
