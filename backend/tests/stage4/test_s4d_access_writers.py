"""Legacy community writers cannot remove staff lifecycle protections."""

import pytest
from django.contrib import admin
from django.core.exceptions import PermissionDenied as AdminPermissionDenied
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.membership_revocation import revoke_membership
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.role_assignments import set_membership_roles
from tests.account_split.p3_helpers import context
from .helpers import bearer_client

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def ctx(settings):
    return context(settings)


@pytest.mark.parametrize("route", ["user-restrict", "user-restore-access"])
@pytest.mark.parametrize("target_name", ["foreign", "worker", "root"])
def test_legacy_access_routes_refuse_staff_and_platform_without_writes(ctx, route, target_name):
    # foreign is the sole active Space Manager in its tenant.
    target = getattr(ctx, target_name)
    before = User.objects.values().get(pk=target.pk)
    memberships = list(MakerspaceMembership.objects.filter(user=target).values())
    api = bearer_client(ctx.root)
    response = api.post(reverse(route, args=[target.pk]),
                        {"status": "suspended", "reason": "Legacy restriction"}, format="json")
    assert response.status_code == 403, response.data
    assert User.objects.values().get(pk=target.pk) == before
    assert list(MakerspaceMembership.objects.filter(user=target).values()) == memberships
    assert not AuditLog.objects.filter(action__in=["user.access_restricted", "user.access_restored"]).exists()


def test_legacy_access_routes_still_restrict_and_restore_community_accounts(ctx):
    api = bearer_client(ctx.root)
    restricted = api.post(reverse("user-restrict", args=[ctx.member.pk]),
                          {"status": "restricted", "reason": "Unreturned tool"}, format="json")
    assert restricted.status_code == 200, restricted.data
    ctx.member.refresh_from_db()
    assert ctx.member.access_status == "restricted"
    restored = api.post(reverse("user-restore-access", args=[ctx.member.pk]), {}, format="json")
    assert restored.status_code == 200, restored.data
    ctx.member.refresh_from_db()
    assert ctx.member.access_status == "active" and not ctx.member.restriction_reason
    assert AuditLog.objects.filter(action="user.access_restricted").exists()
    assert AuditLog.objects.filter(action="user.access_restored").exists()


@pytest.mark.parametrize("action", ["restrict_access", "restore_access", "delete_queryset"])
@pytest.mark.parametrize("target_name", ["foreign", "root"])
def test_control_bulk_writers_refuse_mixed_lifecycle_targets(ctx, action, target_name):
    target = getattr(ctx, target_name)
    before = User.objects.values().get(pk=target.pk)
    request = RequestFactory().post("/control/", {"apply": "1", "status": "suspended", "reason": "Bulk"})
    request.user = ctx.root
    selected = User.objects.filter(pk__in=[ctx.member.pk, target.pk])
    with pytest.raises(AdminPermissionDenied):
        getattr(admin.site._registry[User], action)(request, selected)
    assert User.objects.values().get(pk=target.pk) == before
    ctx.member.refresh_from_db()
    assert ctx.member.access_status == "active"


@pytest.mark.parametrize("operation", ["revoke", "demote"])
def test_legacy_membership_writers_preserve_last_active_manager(ctx, operation):
    membership = MakerspaceMembership.objects.get(user=ctx.foreign, makerspace=ctx.other)
    with pytest.raises(ValidationError, match="last active Space Manager"):
        if operation == "revoke":
            revoke_membership(ctx.root, membership, "Legacy revoke")
        else:
            set_membership_roles(makerspace=ctx.other, actor=ctx.root, membership=membership,
                                 roles=[ctx.other.roles.get(slug="inventory_manager")])
    membership.refresh_from_db()
    ctx.foreign.refresh_from_db()
    assert membership.status == "active" and membership.assigned_role.slug == "space_manager"
    assert ctx.foreign.is_active and ctx.foreign.access_status == "active"
