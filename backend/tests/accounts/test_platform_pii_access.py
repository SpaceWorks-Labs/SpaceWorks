"""Superadmin PII windows: reason, re-auth, 30 minutes, closable, audited (owner #111 Q12)."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import pii_access
from apps.accounts.models import PlatformPiiAccessGrant, User
from apps.accounts.pii_presentation import person_pii_visible, pii_visible
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.stage4.helpers import bearer_client

pytestmark = pytest.mark.django_db
REASON = "Investigating a disputed loan for the space"


@pytest.fixture
def ctx():
    space = Makerspace.objects.create(name="Pii", slug="pii-space")
    other = Makerspace.objects.create(name="Pii other", slug="pii-other")
    root = User.objects.create_superuser("pii-root", email="root@pii.test", password="x" * 20)
    manager = make_staff(space, username="pii-manager")
    inventory = make_staff(space, username="pii-inventory", role_slug="inventory_manager")
    member = User.objects.create_user("pii-member", email="member@pii.test")
    make_membership(member, space)
    make_membership(member, other)
    return type("Ctx", (), dict(space=space, other=other, root=root, manager=manager, inventory=inventory,
                                member=member))


def client(user):
    api = APIClient()
    force_recent_authenticate(api, user)
    return api


def url(space):
    return f"/api/v1/admin/makerspaces/{space.pk}/pii-access"


def test_superadmin_opens_a_thirty_minute_window_with_audit(ctx):
    assert pii_visible(ctx.root, ctx.space.pk) is False
    response = client(ctx.root).post(url(ctx.space), {"reason": REASON}, format="json")
    assert response.status_code == 201, response.data
    active = response.data["active"]
    assert active["reason"] == REASON and response.data["pii_visible"] is True
    grant = PlatformPiiAccessGrant.objects.get()
    assert grant.expires_at - grant.opened_at == timedelta(minutes=30)
    entry = AuditLog.objects.get(action="platform.pii_access_opened")
    assert entry.makerspace == ctx.space and entry.actor == ctx.root
    assert entry.meta["reason"] == REASON and entry.meta["scope"] == "space"
    fresh = User.objects.get(pk=ctx.root.pk)
    assert pii_visible(fresh, ctx.space.pk) is True and pii_visible(fresh, ctx.other.pk) is False


def test_opening_needs_recent_reauth_and_a_real_reason(ctx):
    refused = bearer_client(ctx.root).post(url(ctx.space), {"reason": REASON}, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "recent_reauth_required"
    assert client(ctx.root).post(url(ctx.space), {"reason": "short"}, format="json").status_code == 400
    assert not PlatformPiiAccessGrant.objects.exists()
    assert not AuditLog.objects.filter(action="platform.pii_access_opened").exists()


def test_a_second_window_on_the_same_space_conflicts(ctx):
    api = client(ctx.root)
    assert api.post(url(ctx.space), {"reason": REASON}, format="json").status_code == 201
    assert api.post(url(ctx.space), {"reason": REASON}, format="json").status_code == 409


def test_staff_cannot_open_but_the_space_manager_sees_open_windows(ctx):
    assert client(ctx.manager).post(url(ctx.space), {"reason": REASON}, format="json").status_code == 403
    pii_access.open_grant(ctx.root, ctx.space, REASON)
    seen = client(ctx.manager).get(url(ctx.space))
    assert seen.status_code == 200, seen.data
    assert seen.data["viewer_is_superadmin"] is False and seen.data["active"] is None
    assert [grant["reason"] for grant in seen.data["space_grants"]] == [REASON]
    assert seen.data["space_grants"][0]["opened_by"] == "pii-root"
    assert client(ctx.inventory).get(url(ctx.space)).status_code == 403


def test_close_is_audited_and_hides_pii_again(ctx):
    api = client(ctx.root)
    api.post(url(ctx.space), {"reason": REASON}, format="json")
    response = api.delete(url(ctx.space))
    assert response.status_code == 200, response.data
    assert response.data["active"] is None and response.data["pii_visible"] is False
    entry = AuditLog.objects.get(action="platform.pii_access_closed")
    assert entry.makerspace == ctx.space and entry.meta["close_reason"] == "closed"
    assert api.delete(url(ctx.space)).status_code == 404


def test_expiry_is_closed_and_audited_on_the_next_read(ctx):
    grant = pii_access.open_grant(ctx.root, ctx.space, REASON)
    past = timezone.now() - timedelta(hours=1)
    PlatformPiiAccessGrant.objects.filter(pk=grant.pk).update(opened_at=past, expires_at=past + timedelta(minutes=30))
    response = client(ctx.manager).get(url(ctx.space))
    assert response.data["space_grants"] == []
    grant.refresh_from_db()
    assert grant.close_reason == "expired" and grant.closed_at == grant.expires_at
    entry = AuditLog.objects.get(action="platform.pii_access_closed")
    assert entry.meta["close_reason"] == "expired" and entry.makerspace == ctx.space


def test_pii_audit_rows_are_visible_to_the_space_manager(ctx):
    grant = pii_access.open_grant(ctx.root, ctx.space, REASON)
    pii_access.close_grant(ctx.root, grant)
    response = client(ctx.manager).get("/api/v1/admin/audit-logs", {"makerspace": ctx.space.pk})
    assert response.status_code == 200, response.data
    seen = {item["action"]: item["meta"] for item in response.data["results"]}
    assert seen["platform.pii_access_opened"]["reason"] == REASON
    assert seen["platform.pii_access_closed"]["close_reason"] == "closed"


def test_per_person_reveal_is_audited_in_every_space_they_belong_to(ctx):
    root = User.objects.get(pk=ctx.root.pk)
    assert person_pii_visible(root, ctx.member) is False
    pii_access.open_person_grant(root, ctx.member, REASON)
    rows = AuditLog.objects.filter(action="platform.pii_access_opened")
    assert set(rows.values_list("makerspace_id", flat=True)) == {ctx.space.pk, ctx.other.pk}
    assert set(rows.values_list("target_id", flat=True)) == {str(ctx.member.pk)}
    assert person_pii_visible(root, ctx.member) is True
    assert pii_visible(root, ctx.space.pk) is False  # the person, not the whole space
    with pytest.raises(ValidationError):
        pii_access.open_person_grant(root, ctx.root, REASON)


def test_a_person_is_visible_when_every_space_they_belong_to_is_open(ctx):
    root = User.objects.get(pk=ctx.root.pk)
    pii_access.open_grant(root, ctx.space, REASON)
    assert person_pii_visible(root, ctx.member) is False
    pii_access.open_grant(root, ctx.other, REASON)
    assert person_pii_visible(root, ctx.member) is True
    assert person_pii_visible(root, ctx.root) is True  # platform accounts are not tenant data


def test_grants_are_append_only(ctx):
    grant = pii_access.open_grant(ctx.root, ctx.space, REASON)
    grant.reason = "A different reason entirely"
    with pytest.raises(ValidationError):
        grant.save()
    pii_access.close_grant(ctx.root, grant)
    grant.refresh_from_db()
    grant.closed_at = timezone.now()
    with pytest.raises(ValidationError):
        grant.save(update_fields=["closed_at", "close_reason"])
    with pytest.raises(ValidationError):
        grant.delete()


def test_only_the_opener_closes_a_window(ctx):
    other_root = User.objects.create_superuser("pii-root-2", email="r2@pii.test", password="x" * 20)
    grant = pii_access.open_grant(ctx.root, ctx.space, REASON)
    from rest_framework.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        pii_access.close_grant(other_root, grant)
