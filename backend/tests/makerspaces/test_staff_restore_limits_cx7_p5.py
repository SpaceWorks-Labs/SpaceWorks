"""527.2: retained staff rows own capacity even while revoked or disabled."""
import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.accounts import staff_account_lifecycle as lifecycle, staff_account_services as staff
from apps.audit.models import AuditLog
from apps.makerspaces.limits_usage import _staff
from apps.makerspaces.models import MakerspaceMembership
from tests.makerspaces.test_admission_limits_cx7_p4b import staff_world, staff_admit
from tests.makerspaces.test_admission_http_limits_cx7_p4b import staff_pair
from tests.limits_0120.creator_races_cx7 import race_creators

pytestmark = [pytest.mark.django_db, pytest.mark.area_staff_admin, pytest.mark.area_membership]


def setup(monkeypatch):
    w = staff_world("grant", monkeypatch)
    space, actor, people, _, _ = w
    staff_admit(w, "grant", 0)
    row = MakerspaceMembership.staff_tracks.get(makerspace=space, user=people[0])
    lifecycle.revoke(actor, space.pk, row.pk)
    assert _staff(space) == w[4] + 1
    return w, row


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_restore_at_max_consumes_no_slot_and_next_grant_is_refused(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    w, row = setup(monkeypatch)
    space, actor, people, _, _ = w
    pair = staff_pair(space, actor, surface, settings, monkeypatch)
    maximum = _staff(space)
    space.resource_limit_overrides = {"staff": maximum}
    space.save(update_fields=["resource_limit_overrides"])
    base = f"/api/v1/admin/makerspaces/{space.pk}/staff-roles/"
    restored = pair[0].post(f"{base}{row.pk}/restore/", {}, format="json")
    assert restored.status_code == 200
    assert _staff(space) == maximum
    before = list(MakerspaceMembership.staff_tracks.order_by("pk").values())
    refused = pair[0].post(base, {"user_id": people[1].pk, "roles": ["inventory_manager"]}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (409, "quota_exceeded")
    assert list(MakerspaceMembership.staff_tracks.order_by("pk").values()) == before
    assert AuditLog.objects.filter(action="staff_role.restored", makerspace=space).count() == 1


def test_disabled_staff_remains_counted_before_account_enable(settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    w, row = setup(monkeypatch)
    maximum = _staff(w[0])
    row.user.is_active = False
    row.user.save(update_fields=["is_active"])
    assert _staff(w[0]) == maximum
    with pytest.raises(APIException) as failure:
        staff.grant(w[1], w[0].pk, user_id=w[2][1].pk, roles=["inventory_manager"])
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (409, "quota_exceeded")


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_restore_when_retained_count_is_max_plus_one_is_refused_without_authority_change(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    w, row = setup(monkeypatch)
    space, actor = w[:2]
    pair = staff_pair(space, actor, surface, settings, monkeypatch)
    space.resource_limit_overrides = {"staff": _staff(space) - 1}
    space.save(update_fields=["resource_limit_overrides"])
    before = list(MakerspaceMembership.staff_tracks.order_by("pk").values())
    url = f"/api/v1/admin/makerspaces/{space.pk}/staff-roles/{row.pk}/restore/"
    refused = pair[0].post(url, {}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (409, "quota_exceeded")
    assert list(MakerspaceMembership.staff_tracks.order_by("pk").values()) == before
    assert AuditLog.objects.filter(action="staff_role.restored", makerspace=space).count() == 0


@pytest.mark.django_db(transaction=True)
def test_restore_and_new_grant_share_the_full_retained_cap(settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    w, row = setup(monkeypatch)
    commands = [lambda: lifecycle.restore(w[1], w[0].pk, row.pk),
                lambda: staff.grant(w[1], w[0].pk, user_id=w[2][1].pk, roles=["inventory_manager"])]
    assert race_creators(lambda index: commands[index]()) == [(201, "created"), (409, "quota_exceeded")]
    assert _staff(w[0]) == w[4] + 1


def test_control_cannot_restore_staff_by_editing_the_membership_row(client, monkeypatch):
    from django.contrib import admin
    from django.test import RequestFactory
    from django.urls import reverse
    from tests.accounts.reauth_helpers import force_recent_control_login
    from tests.r2_superadmin_local.helpers import superadmin
    w, row = setup(monkeypatch)
    root = superadmin("p5-staff-control-root")
    force_recent_control_login(client, root)
    request = RequestFactory().post("/control/")
    request.user = root
    registered = admin.site._registry[MakerspaceMembership]
    assert registered.has_add_permission(request) is False
    assert registered.has_change_permission(request, row) is False
    url = reverse("admin:makerspaces_makerspacemembership_change", args=[row.pk])
    # The default community-only manager deliberately conceals staff-track rows.
    hidden = client.get(url)
    assert (hidden.status_code, hidden.url) == (302, reverse("admin:index"))
    refused = client.post(url, {"status": "active", "_save": "Save"})
    assert (refused.status_code, refused.url) == (302, reverse("admin:index"))
    row.refresh_from_db()
    assert row.status == "revoked"
    assert _staff(w[0]) == w[4] + 1
