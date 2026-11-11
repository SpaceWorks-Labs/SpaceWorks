"""Decision 246: staff presence (roster, check-in, check-out, privacy) across every built-in role.

Roster, check-in and check-out need `manage_members`; the privacy settings need `manage_makerspace`
(`presence/policy.require_staff`). Expectations are derived from `ROLE_CATALOG`. Check-in is idempotent
(one live session), check-out of someone not present is a 404, and every route is 404 with the module off.
"""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from apps.presence.models import PresenceSession
from tests.fixed_roles.helpers import staff_account
from tests.presence.test_presence_m3 import member
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db(transaction=True)
SLUGS = [role.slug for role in ROLE_CATALOG]


def _space(slug, presence=True):
    space = make_space(slug)
    modules = set(space.enabled_modules or [])
    space.enabled_modules = sorted(modules | {"presence"} if presence else modules - {"presence"})
    space.save(update_fields=["enabled_modules"])
    return space


def _url(space, tail):
    return f"/api/v1/admin/makerspace/{space.pk}/presence-sessions/{tail}"


def _holds(slug, action):
    return action in ROLE_BY_SLUG[slug].granted_actions


@pytest.mark.parametrize("slug", SLUGS)
def test_roster_check_in_and_check_out_follow_manage_members(slug):
    space = _space(f"pre-{slug}".replace("_", "-"))
    person, _membership = member(space, f"pre-person-{slug}")
    client = authenticated_client(staff_account(space, f"pre-actor-{slug}", slug))
    roster = client.get(_url(space, "current"))
    checked_in = client.post(_url(space, "check-in"), {"account_id": person.pk, "duration_minutes": 60}, format="json")
    checked_out = client.post(_url(space, "check-out"), {"account_id": person.pk}, format="json")
    if _holds(slug, "manage_members"):
        assert roster.status_code == 200
        assert checked_in.status_code == 201, checked_in.content
        assert checked_out.status_code == 200, checked_out.content
        assert PresenceSession.objects.filter(makerspace=space, account=person, ended_at__isnull=False).exists()
    else:
        for refused in (roster, checked_in, checked_out):
            assert refused.status_code in (403, 404)
        assert not PresenceSession.objects.filter(makerspace=space).exists()


@pytest.mark.parametrize("slug", SLUGS)
def test_privacy_settings_follow_manage_makerspace(slug):
    space = _space(f"prp-{slug}".replace("_", "-"))
    client = authenticated_client(staff_account(space, f"prp-actor-{slug}", slug))
    read = client.get(_url(space, "privacy"))
    assert (read.status_code == 200) is _holds(slug, "manage_makerspace")
    if not _holds(slug, "manage_makerspace"):
        assert read.status_code in (403, 404)
        assert client.patch(_url(space, "privacy"), {"show_names": True, "allow_personal_opt_out": True}, format="json").status_code in (403, 404)


def test_checking_in_twice_keeps_one_live_session_and_checking_out_twice_is_404():
    space = _space("pre-idem")
    person, _m = member(space, "pre-idem-person")
    boss = authenticated_client(staff_account(space, "pre-idem-boss", "space_manager"))
    body = {"account_id": person.pk, "duration_minutes": 60}
    assert boss.post(_url(space, "check-in"), body, format="json").status_code == 201
    boss.post(_url(space, "check-in"), body, format="json")
    assert PresenceSession.objects.filter(makerspace=space, account=person, ended_at__isnull=True).count() == 1
    assert boss.post(_url(space, "check-out"), {"account_id": person.pk}, format="json").status_code == 200
    assert boss.post(_url(space, "check-out"), {"account_id": person.pk}, format="json").status_code == 404
    assert PresenceSession.objects.filter(makerspace=space, account=person, ended_at__isnull=True).count() == 0


@pytest.mark.parametrize("body", [{}, {"account_id": 0, "duration_minutes": 60}, {"account_id": "x", "duration_minutes": 60},
                                  {"account_id": 1, "duration_minutes": 5}, {"account_id": 1, "duration_minutes": 9999},
                                  {"account_id": 1, "duration_minutes": 60, "status": "dancing"}])
def test_check_in_validation_is_400_and_creates_no_session(body):
    space = _space("pre-valid")
    boss = authenticated_client(staff_account(space, "pre-valid-boss", "space_manager"))
    assert boss.post(_url(space, "check-in"), body, format="json").status_code == 400
    assert not PresenceSession.objects.exists()


def test_an_account_unknown_to_this_space_is_404_not_a_probe():
    mine, theirs = _space("pre-iso-a"), _space("pre-iso-b")
    stranger, _m = member(theirs, "pre-iso-stranger")
    boss = authenticated_client(staff_account(mine, "pre-iso-boss", "space_manager"))
    assert boss.post(_url(mine, "check-in"), {"account_id": stranger.pk, "duration_minutes": 60}, format="json").status_code == 404
    assert boss.post(_url(mine, "check-in"), {"account_id": 99999999, "duration_minutes": 60}, format="json").status_code == 404
    assert not PresenceSession.objects.exists()


def test_another_spaces_manager_and_anonymous_are_refused_everywhere():
    mine, theirs = _space("pre-x-a"), _space("pre-x-b")
    person, _m = member(mine, "pre-x-person")
    outsider = authenticated_client(staff_account(theirs, "pre-x-out", "space_manager"))
    for client, refused in ((outsider, (403, 404)), (APIClient(), (401, 403))):
        assert client.get(_url(mine, "current")).status_code in refused
        assert client.post(_url(mine, "check-in"), {"account_id": person.pk, "duration_minutes": 60},
                           format="json").status_code in refused
        assert client.get(_url(mine, "privacy")).status_code in refused
    assert not PresenceSession.objects.exists()


def test_every_staff_presence_route_is_404_while_the_module_is_off():
    space = _space("pre-off", presence=False)
    person, _m = member(space, "pre-off-person")
    boss = authenticated_client(staff_account(space, "pre-off-boss", "space_manager"))
    assert boss.get(_url(space, "current")).status_code == 404
    assert boss.get(_url(space, "privacy")).status_code == 404
    assert boss.post(_url(space, "check-in"), {"account_id": person.pk, "duration_minutes": 60}, format="json").status_code == 404
    assert not PresenceSession.objects.exists()
    assert not AuditLog.objects.filter(makerspace=space, action__startswith="presence").exists()
