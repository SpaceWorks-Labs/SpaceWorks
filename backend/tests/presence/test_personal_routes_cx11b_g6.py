"""Presence identity is an account with optional membership (INVARIANTS / decision 223)."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.makerspaces.models import MakerspaceMembership
from apps.presence.models import PresenceSession
from tests.notifications.routes_support_cx11b_g6 import cycle, send, world
from tests.presence.routes_support_cx11b_g6 import seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_presence]
OPS = [("start", "post", "presence-start"), ("current", "get", "presence-current"),
       ("end", "post", "presence-end"), ("renew", "post", "presence-renew"),
       ("projects", "get", "presence-projects"), ("preferences-get", "get", "presence-preferences"),
       ("preferences-patch", "patch", "presence-preferences")]
CASES = [(op, key, native, guest) for op in OPS for key in
         (["presence", "presence.geofence"] if op[0] == "start" else ["presence"])
         for native in (False, True) for guest in (False, True)]


@pytest.mark.parametrize("op,key,native,guest", CASES)
def test_personal_presence_exact_owned_effect_and_nonmember_contract(op, key, native, guest, monkeypatch):
    name, method, route = op
    space, owner, client, outsider, foreign = world(native)
    person, caller = (outsider, foreign) if guest else (owner, client)
    assert MakerspaceMembership.objects.filter(makerspace=space, user=person).exists() is (not guest)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    row, preference, project = seed(space, person, session=name != "start")
    url = reverse(route, kwargs={"makerspace_slug": space.slug})
    body = {"duration_minutes": 60, "latitude": 0, "longitude": 0, "accuracy": 5} if name == "start" else (
        {"duration_minutes": 120} if name == "renew" else {"hide_on_display": True} if name == "preferences-patch" else {})
    actions = {"start": "presence.started", "end": "presence.ended", "renew": "presence.renewed",
               "preferences-patch": "presence.preference_updated"}
    def check(response):
        if name == "start":
            saved = PresenceSession.objects.get(makerspace=space, account=person)
            assert (saved.member_id, saved.status, saved.started_at, saved.expires_at) == (
                person.pk, "guest" if guest else "visiting", now, now + timedelta(minutes=60))
            assert saved.membership_id == (None if guest else MakerspaceMembership.objects.get(
                makerspace=space, user=person).pk)
            assert response.data["active"] is True and response.data["status"] == saved.status
        elif name == "current":
            assert response.data["active"] is True
            assert response.data["session"]["status"] == ("guest" if guest else "visiting")
            assert parse_datetime(response.data["session"]["started_at"]) == row.started_at
        elif name == "end":
            row.refresh_from_db()
            assert (row.ended_at, row.end_reason, row.ended_by_id) == (now, "user_ended", person.pk)
            assert response.data["active"] is False and response.data["session"] is None
        elif name == "renew":
            row.refresh_from_db()
            assert (row.expires_at, row.revision, row.ended_at) == (now + timedelta(minutes=120), 2, None)
            assert response.data["active"] is True
        elif name == "projects":
            assert response.data["count"] == 1
            assert response.data["results"] == [{"id": project.pk, "title": "G6 private project", "public_visible": False}]
        else:
            preference.refresh_from_db()
            assert response.data == {"hide_on_display": name == "preferences-patch"}
            assert preference.hide_on_display is (name == "preferences-patch")
            if name == "preferences-patch":
                row.refresh_from_db()
                assert row.hide_on_display is True
        assert not PresenceSession.objects.filter(makerspace=space).exclude(account=person).exists()
    if native and guest:
        # A nonmember cannot select this tenant (494). Preserve that refusal, then
        # exercise the documented account-only flow with an unselected member grant.
        from tests.modules.switch_matrix_object_helpers import response_pair
        from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes
        with no_domain_writes():
            refused = send(caller, method, url, body)
        assert response_pair(refused) == (403, "permission_denied"), refused.data
        caller._credentials.pop("HTTP_X_MAKERSPACE_ID")
    cycle(space, key, lambda: send(caller, method, url, body), check,
          on=(201 if name == "start" else 200, None),
          off=(400, "geofence_unconfigured") if key == "presence.geofence" else (404, "not_found"),
          actions=(actions[name],) if name in actions else ())
