"""Presence staff operations: exact effects/audits and 481/494 foreign standing."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.models import GuestPass
from apps.presence.models import PresenceSession, PresenceSettings
from tests.notifications.routes_support_cx11b_g6 import cycle, hidden, send, world
from tests.presence.routes_support_cx11b_g6 import member, seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_presence]
OPS = [
    ("start", "post", "admin-presence-start"), ("end", "post", "admin-presence-end"),
    ("roster", "get", "admin-presence-sessions-current"),
    ("privacy-get", "get", "admin-presence-privacy"), ("privacy-patch", "patch", "admin-presence-privacy"),
    ("guests", "get", "admin-presence-check-in-guests"),
    ("config-get", "get", "admin-presence-now-config"), ("config-put", "put", "admin-presence-now-config"),
]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("op,key", [(op, key) for op in OPS for key in
    (["presence", "membership", "member_accounts", "membership.guest_passes"] if op[0] == "guests" else ["presence"])])
def test_staff_presence_operation_retains_rows_and_refuses_foreign_before_gate(op, key, native, monkeypatch):
    name, method, route = op
    space, actor, client, stranger, foreign = world(native, staff=True)
    person = member(space)
    person.display_name = "G6 present person"
    person.save(update_fields=["display_name"])
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    row, preference, project = seed(space, person, session=name != "start")
    body = {"account_id": person.pk, "duration_minutes": 60} if name == "start" else (
        {"account_id": person.pk} if name == "end" else {"show_names": False, "allow_personal_opt_out": False}
        if name == "privacy-patch" else {"q": "G6"} if name == "guests" else
        {"sections": ["opening_hours"], "privacy": "counts", "refresh_seconds": 60} if name == "config-put" else {})
    if name == "guests":
        GuestPass.objects.create(makerspace=space, holder=person, kind="day", valid_from=now - timedelta(minutes=1),
            valid_until=now + timedelta(hours=3), pass_date=now.date(), entitlements={"presence": True})
    from apps.presence.models_anthias import SpaceNowConfig
    config = SpaceNowConfig.objects.create(makerspace=space, sections=["here_now"], privacy="profiles", refresh_seconds=30)
    url = reverse(route, kwargs={"makerspace_id": space.pk})
    def check(response):
        if name == "start":
            saved = PresenceSession.objects.get(makerspace=space, account=person)
            assert (saved.started_at, saved.expires_at, saved.status) == (now, now + timedelta(minutes=60), "visiting")
            assert response.data["active"] is True
        elif name == "end":
            row.refresh_from_db()
            assert (row.ended_at, row.end_reason, row.ended_by_id) == (now, "staff_ended", actor.pk)
            assert response.data["active"] is False
        elif name == "roster":
            assert response.data["count"] == 1
            assert [(r["account_id"], r["display_name"]) for r in response.data["results"]] == [(person.pk, "G6 present person")]
        elif name.startswith("privacy"):
            policy = PresenceSettings.objects.get(makerspace=space)
            expected = name == "privacy-get"
            assert (policy.show_names, policy.allow_personal_opt_out) == (expected, expected)
            assert response.data == {"show_names": expected, "allow_personal_opt_out": expected}
        elif name == "guests":
            assert response.data == {"results": [{"id": person.pk, "display_name": "G6 present person",
                "pass_valid_until": now + timedelta(hours=3), "waiver_on_file": False}]}
        else:
            config.refresh_from_db()
            expected = body if name == "config-put" else {"sections": ["here_now"], "privacy": "profiles", "refresh_seconds": 30}
            assert response.data == expected
            assert (config.sections, config.privacy, config.refresh_seconds) == (
                expected["sections"], expected["privacy"], expected["refresh_seconds"])
    action = {"start": "presence.started", "end": "presence.ended", "privacy-patch": "presence.settings_updated",
              "config-put": "presence.now_config_updated"}.get(name)
    def off_check(response):
        assert response.data == {"results": []}
    fallback = name == "guests" and key != "presence"
    cycle(space, key, lambda: send(client, method, url, body), check,
          on=(201 if name == "start" else 200, None), actions=(action,) if action else (),
          off=(200, None) if fallback else (404, "not_found"), off_check=off_check if fallback else None,
          probes=[hidden(lambda: send(foreign, method, url, body), native_staff=native)])
