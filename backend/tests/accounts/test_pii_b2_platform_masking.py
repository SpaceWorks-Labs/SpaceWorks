"""B2: the PII-window expiry sweep and masking on platform routes (#111 Q12, #114)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts import pii_access
from apps.accounts.models import PlatformPiiAccessGrant, User
from apps.accounts.pii_presentation import MASK
from apps.accounts.tasks import expire_pii_access_windows_task
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.reauth_helpers import force_recent_authenticate

pytestmark = pytest.mark.django_db
REASON = "Checking a disputed membership for the space"


@pytest.fixture
def ctx():
    space = Makerspace.objects.create(name="Mask", slug="b2-mask")
    root = User.objects.create_superuser("b2-root", email="root@b2.test", password="x" * 20)
    manager = make_staff(space, username="b2-manager", email="manager@b2.test")
    member = User.objects.create_user("b2-member", email="member@b2.test", first_name="Mia")
    make_membership(member, space)
    return type("Ctx", (), dict(space=space, root=root, manager=manager, member=member))


def api(user):
    from rest_framework.test import APIClient
    client = APIClient()
    force_recent_authenticate(client, user)
    return client


def _staff_url(ctx):
    from django.urls import reverse
    return reverse("admin-staff-roles", args=[ctx.space.pk])  # U-B: staff-roles replaced staff-accounts


def _lapse(grant, minutes=1):
    PlatformPiiAccessGrant.objects.filter(pk=grant.pk).update(
        opened_at=timezone.now() - timedelta(minutes=31 + minutes),
        expires_at=timezone.now() - timedelta(minutes=minutes))


def test_beat_sweep_closes_lapsed_windows_at_their_expiry_and_audits(ctx):
    lapsed = pii_access.open_grant(ctx.root, ctx.space, REASON)
    _lapse(lapsed)
    lapsed.refresh_from_db()
    assert expire_pii_access_windows_task() == 1
    lapsed.refresh_from_db()
    assert lapsed.closed_at == lapsed.expires_at and lapsed.close_reason == "expired"
    entry = AuditLog.objects.get(action="platform.pii_access_closed")
    assert entry.makerspace == ctx.space and entry.meta["close_reason"] == "expired"
    assert expire_pii_access_windows_task() == 0


def test_beat_sweep_leaves_open_windows_and_is_bounded(ctx, monkeypatch):
    open_now = pii_access.open_grant(ctx.root, ctx.space, REASON)
    assert expire_pii_access_windows_task() == 0
    open_now.refresh_from_db()
    assert open_now.closed_at is None
    _lapse(open_now)
    monkeypatch.setattr("apps.accounts.tasks.PII_EXPIRY_BATCH", 0)
    assert expire_pii_access_windows_task() == 0


def test_staff_account_list_masks_staff_for_a_superadmin_without_a_window(ctx):
    url = _staff_url(ctx)
    rows = api(ctx.root).get(url).data["results"]
    row = next(item for item in rows if item["username"] == "b2-manager")
    assert row["email"] == MASK and row["pii_masked"] is True
    pii_access.open_grant(ctx.root, ctx.space, REASON)
    rows = api(User.objects.get(pk=ctx.root.pk)).get(url).data["results"]
    row = next(item for item in rows if item["username"] == "b2-manager")
    assert row["email"] != MASK and "pii_masked" not in row


def test_space_manager_sees_staff_unmasked(ctx):
    url = _staff_url(ctx)
    response = api(ctx.manager).get(url)
    assert response.status_code == 200, response.data
    assert all(item["email"] != MASK for item in response.data["results"])


def test_user_serializer_on_a_platform_route_masks_by_person(ctx):
    from rest_framework.test import APIRequestFactory

    from apps.admin_api.serializers_users import UserSerializer

    request = APIRequestFactory().get("/")
    request.user = ctx.root
    data = UserSerializer(ctx.member, context={"request": request}).data
    assert data["email"] == MASK and data["first_name"] == MASK and data["pii_masked"] is True
    pii_access.open_person_grant(ctx.root, ctx.member, REASON)
    request.user = User.objects.get(pk=ctx.root.pk)
    data = UserSerializer(ctx.member, context={"request": request}).data
    assert data["email"] == "member@b2.test" and "pii_masked" not in data


def test_disclosure_closure_masks_identities_but_keeps_the_real_digest(ctx):
    from apps.tenant_migration.admission import compute_pending_closure

    from django.urls import reverse
    url = reverse("tenant-migration-disclosure-closure", args=[ctx.space.pk])
    response = api(ctx.root).get(url)
    assert response.status_code == 200, response.data
    assert response.data["digest"] == compute_pending_closure(ctx.space)["digest"]
    masked = [item for item in response.data["identities"] if item.get("pii_masked")]
    assert masked and all(item["email"] == MASK for item in masked)
