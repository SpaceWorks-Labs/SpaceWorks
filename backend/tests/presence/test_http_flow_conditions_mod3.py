"""MOD-3 flow audit: the member presence HTTP flow, one assertion per condition.

Start / current / renew / end over the real routes: module switch, signed-out, other tenant,
boundaries (min/max duration, unknown preset), malformed input, idempotent start, audit once.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.presence.models import PresenceSession
from .fence_helpers import INSIDE, fence

pytestmark = pytest.mark.django_db(transaction=True)


def _space(slug):
    return fence(Makerspace.objects.create(name=slug, slug=slug, enabled_modules=["presence"]))


def _member(space, username):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="password")
    role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    MakerspaceMembership.objects.create(makerspace=space, user=user, assigned_role=role, role="custom", status="active")
    return user


def _api(user=None):
    api = APIClient()
    if user:
        api.force_authenticate(user)
    return api


def _url(space, tail=""):
    return f"/api/v1/public/{space.slug}/presence-sessions{tail}"


def _audits(space, action):
    return AuditLog.objects.filter(makerspace=space, action=action).count()


def test_start_current_renew_end_each_audit_exactly_once_and_start_retry_is_idempotent():
    space = _space("mod3-pres-a")
    user = _member(space, "mod3-pres-a-user")
    api = _api(user)
    body = {"duration_minutes": 60, **INSIDE}
    first = api.post(_url(space), body, format="json")
    assert first.status_code == 201, first.data
    retry = api.post(_url(space), body, format="json")  # double click / network retry
    assert retry.status_code == 201 and retry.data == first.data
    assert PresenceSession.objects.filter(account=user, makerspace=space).count() == 1
    assert _audits(space, "presence.started") == 1
    assert api.get(_url(space, "/current")).data["active"] is True
    renewed = api.post(_url(space, "/current/renew"), {"duration_minutes": 120}, format="json")
    assert renewed.status_code == 200, renewed.data
    assert _audits(space, "presence.renewed") == 1
    ended = api.post(_url(space, "/current/end"))
    assert ended.status_code == 200 and ended.data["active"] is False
    assert _audits(space, "presence.ended") == 1
    assert api.get(_url(space, "/current")).data["active"] is False


@pytest.mark.parametrize("duration", [60.5, None, "abc", 14, 481, 45])
def test_start_refuses_malformed_and_out_of_preset_durations(duration):
    space = _space("mod3-pres-b")
    user = _member(space, "mod3-pres-b-user")
    response = _api(user).post(_url(space), {"duration_minutes": duration, **INSIDE}, format="json")
    assert response.status_code == 400
    assert not PresenceSession.objects.filter(makerspace=space).exists()
    assert _audits(space, "presence.started") == 0


def test_renew_bounds_are_the_serializer_bounds_15_to_480():
    space = _space("mod3-pres-b2")
    api = _api(_member(space, "mod3-pres-b2-user"))
    assert api.post(_url(space), {"duration_minutes": 60, **INSIDE}, format="json").status_code == 201
    for bad in (0, 14, 481, -60):
        assert api.post(_url(space, "/current/renew"), {"duration_minutes": bad}, format="json").status_code == 400
    assert _audits(space, "presence.renewed") == 0


@pytest.mark.parametrize("extra", [{"status": "<script>alert(1)</script>"}, {"status": "работа"},
                                   {"hide_on_display": "maybe"}, {"project_id": 0}, {"unknown_field": 1},
                                   {"latitude": 91}, {"longitude": "NaN"}])
def test_start_refuses_hostile_or_unknown_input_without_writing(extra):
    space = _space("mod3-pres-c")
    api = _api(_member(space, "mod3-pres-c-user"))
    response = api.post(_url(space), {"duration_minutes": 60, **INSIDE, **extra}, format="json")
    assert response.status_code == 400, response.data
    assert not PresenceSession.objects.filter(makerspace=space).exists()


def test_signed_out_callers_are_refused_on_every_member_route():
    space = _space("mod3-pres-d")
    api = _api()
    for method, tail in (("post", ""), ("get", "/current"), ("post", "/current/end"), ("post", "/current/renew")):
        assert getattr(api, method)(_url(space, tail), {"duration_minutes": 60}, format="json").status_code in (401, 403), tail


def test_member_of_another_space_checks_in_here_only_as_a_guest_never_as_a_member():
    here, there = _space("mod3-pres-e1"), _space("mod3-pres-e2")
    outsider = _member(there, "mod3-pres-e-user")
    response = _api(outsider).post(_url(here), {"duration_minutes": 60, **INSIDE}, format="json")
    assert response.status_code == 201, response.data
    row = PresenceSession.objects.get(makerspace=here, account=outsider)
    assert row.status == "guest" and row.membership_id is None
    assert not PresenceSession.objects.filter(makerspace=there).exists()  # nothing leaks into their own space


def test_module_off_is_404_everywhere_and_turning_it_on_restores_with_data_kept():
    space = _space("mod3-pres-f")
    user = _member(space, "mod3-pres-f-user")
    api = _api(user)
    assert api.post(_url(space), {"duration_minutes": 60, **INSIDE}, format="json").status_code == 201
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=[])
    for method, tail in (("post", ""), ("get", "/current"), ("post", "/current/end"), ("post", "/current/renew")):
        assert getattr(api, method)(_url(space, tail), {"duration_minutes": 60, **INSIDE}, format="json").status_code == 404, tail
    assert PresenceSession.objects.filter(account=user, makerspace=space, ended_at=None).count() == 1
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=["presence"])
    assert api.get(_url(space, "/current")).data["active"] is True


def test_restricted_and_revoked_accounts_are_refused():
    space = _space("mod3-pres-g")
    restricted = _member(space, "mod3-pres-g-r")
    User.objects.filter(pk=restricted.pk).update(access_status="restricted")
    restricted.refresh_from_db()
    assert _api(restricted).post(_url(space), {"duration_minutes": 60, **INSIDE}, format="json").status_code == 403
    revoked = _member(space, "mod3-pres-g-v")
    MakerspaceMembership.objects.filter(user=revoked, makerspace=space).update(status="revoked")
    response = _api(revoked).post(_url(space), {"duration_minutes": 60, **INSIDE}, format="json")
    assert response.status_code == 403
    assert not PresenceSession.objects.filter(makerspace=space).exists()


def test_outside_the_geofence_and_missing_location_are_refused():
    space = _space("mod3-pres-h")
    api = _api(_member(space, "mod3-pres-h-user"))
    far = api.post(_url(space), {"duration_minutes": 60, "latitude": 10, "longitude": 10, "accuracy": 5}, format="json")
    assert far.status_code in (400, 403)
    assert api.post(_url(space), {"duration_minutes": 60}, format="json").status_code in (400, 403)
    assert not PresenceSession.objects.filter(makerspace=space).exists()
