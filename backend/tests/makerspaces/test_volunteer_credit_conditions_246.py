"""Decision 246: role, switch, validation, replay and isolation matrix for volunteer hours and credits."""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership, VolunteerHourEntry
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.makerspaces.l4_helpers import features_off, features_on
from tests.makerspaces.test_membership_j1 import member_role, space, user

pytestmark = pytest.mark.django_db(transaction=True)
SLUGS = [role.slug for role in ROLE_CATALOG]


def _client(account):
    client = APIClient()
    client.force_authenticate(account)
    return client


def _ready(slug):
    makerspace = space(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    features_on(makerspace, "volunteer_credit")
    return makerspace


def _member(makerspace, name):
    account = user(name)
    MakerspaceMembership.objects.create(
        makerspace=makerspace, user=account, assigned_role=member_role(makerspace), role="custom",
        status="active", activated_at=timezone.now())
    return account


def _today():
    return timezone.localdate().isoformat()


def _base(makerspace):
    return f"/api/v1/admin/makerspaces/{makerspace.pk}/volunteer-hours"


@pytest.mark.parametrize("slug", SLUGS)
def test_staff_volunteer_list_and_logging_follow_manage_members(slug):
    makerspace = _ready(f"vol-role-{slug}".replace("_", "-"))
    member = _member(makerspace, f"vol-m-{slug}")
    client = _client(staff_account(makerspace, f"vol-actor-{slug}", slug))
    allowed = "manage_members" in ROLE_BY_SLUG[slug].granted_actions
    listed = client.get(_base(makerspace))
    logged = client.post(_base(makerspace), {"member_id": member.pk, "minutes": 30, "worked_on": _today()}, format="json")
    assert (listed.status_code == 200) is allowed
    assert (logged.status_code == 201) is allowed
    if not allowed:
        assert listed.status_code in (403, 404) and logged.status_code in (403, 404)
        assert not VolunteerHourEntry.objects.filter(makerspace=makerspace).exists()


def test_every_volunteer_route_is_404_while_the_capability_is_off_and_nothing_is_written():
    makerspace = _ready("vol-off")
    member = _member(makerspace, "vol-off-m")
    boss = _client(staff_account(makerspace, "vol-off-boss", "space_manager"))
    features_off(makerspace, "volunteer_credit")
    assert boss.get(_base(makerspace)).status_code == 404
    assert boss.post(_base(makerspace), {"member_id": member.pk, "minutes": 30, "worked_on": _today()},
                     format="json").status_code == 404
    mine = _client(member)
    assert mine.get(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-hours").status_code == 404
    assert mine.post(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-hours",
                     {"minutes": 30, "worked_on": _today()}, format="json").status_code == 404
    assert mine.get(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-credits").status_code == 404
    assert not VolunteerHourEntry.objects.exists()


@pytest.mark.parametrize("body", [
    {"minutes": 0}, {"minutes": 1441}, {"minutes": "ninety"}, {"minutes": 30, "worked_on": "2999-01-01"},
    {"minutes": 30, "worked_on": "not-a-date"}, {},
])
def test_member_hours_validation_rejects_bad_minutes_and_future_or_missing_days(body):
    makerspace = _ready("vol-valid")
    member = _member(makerspace, "vol-valid-m")
    body = {"worked_on": _today(), **body} if "worked_on" not in body and body else body
    response = _client(member).post(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-hours", body, format="json")
    assert response.status_code == 400
    assert not VolunteerHourEntry.objects.exists()


def test_non_member_cannot_log_hours_and_member_cannot_decide_their_own_entry():
    makerspace = _ready("vol-auth")
    outsider = user("vol-auth-outsider")
    member = _member(makerspace, "vol-auth-m")
    refused = _client(outsider).post(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-hours",
                                     {"minutes": 30, "worked_on": _today()}, format="json")
    assert refused.status_code in (400, 403, 409)
    created = _client(member).post(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-hours",
                                   {"minutes": 30, "worked_on": _today()}, format="json")
    assert created.status_code == 201 and created.json()["status"] == "pending"
    decide = _client(member).post(f"{_base(makerspace)}/{created.json()['id']}/decide", {"approve": True}, format="json")
    assert decide.status_code in (403, 404)
    assert VolunteerHourEntry.objects.get().status == "pending"


def test_a_decision_is_made_once_audited_once_and_replay_is_409():
    makerspace = _ready("vol-once")
    member = _member(makerspace, "vol-once-m")
    boss = _client(staff_account(makerspace, "vol-once-boss", "space_manager"))
    entry_id = _client(member).post(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-hours",
                                    {"minutes": 60, "worked_on": _today()}, format="json").json()["id"]
    url = f"{_base(makerspace)}/{entry_id}/decide"
    assert boss.post(url, {"approve": True}, format="json").status_code == 200
    again = boss.post(url, {"approve": False}, format="json")
    assert again.status_code == 409
    assert VolunteerHourEntry.objects.get(pk=entry_id).status == "approved"
    assert AuditLog.objects.filter(makerspace=makerspace, action="membership.volunteer_hours_decided").count() == 1


def test_another_spaces_manager_and_entries_are_isolated():
    mine, theirs = _ready("vol-iso-a"), _ready("vol-iso-b")
    member = _member(theirs, "vol-iso-m")
    entry_id = _client(member).post(f"/api/v1/member/makerspaces/{theirs.pk}/volunteer-hours",
                                    {"minutes": 60, "worked_on": _today()}, format="json").json()["id"]
    my_boss = _client(staff_account(mine, "vol-iso-boss", "space_manager"))
    assert my_boss.get(_base(theirs)).status_code in (403, 404)
    assert my_boss.post(f"{_base(mine)}/{entry_id}/decide", {"approve": True}, format="json").status_code == 404
    assert my_boss.post(f"{_base(theirs)}/{entry_id}/decide", {"approve": True}, format="json").status_code in (403, 404)
    assert VolunteerHourEntry.objects.get(pk=entry_id).status == "pending"
    assert my_boss.get(_base(mine)).json()["count"] == 0
