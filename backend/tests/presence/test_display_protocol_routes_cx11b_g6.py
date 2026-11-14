"""Display protocol uses its own bearer secret, independently of person/native grants."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.presence.display_pairing import digest
from apps.presence.models_display import DisplayScreen
from tests.notifications.routes_support_cx11b_g6 import cycle, hidden, send, world
from tests.presence.routes_support_cx11b_g6 import seed
from tests.presence.test_related_routes_cx11b_g6 import neighbours

pytestmark = [pytest.mark.django_db, pytest.mark.area_presence]


@pytest.mark.parametrize("route", ["space-display-state-header", "space-display-state"])
@pytest.mark.parametrize("key", ["presence", "presence.public_display", "machines", "events"])
@pytest.mark.parametrize("native", [False, True], ids=["browser", "native-carrier"])
def test_display_state_bearer_reveals_exact_seeded_panels_and_records_heartbeat(route, key, native, monkeypatch):
    space, actor, carrier, stranger, _foreign = world(native)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    row, preference, project = seed(space, actor)
    event, booking, machine_session = neighbours(space, actor, row)
    token = "g6-protocol-secret"
    screen = DisplayScreen.objects.create(makerspace=space, name="G6 panel screen", token_digest=digest(token),
        code_expires_at=now, claimed_at=now, panels=["here_now", "machines", "calendar", "announcement"], announcement="G6 public announcement")
    client, bad = carrier if native else APIClient(), APIClient()
    url = reverse(route, kwargs={"token": token} if route == "space-display-state" else {})
    bad_url = reverse(route, kwargs={"token": "wrong-g6-secret"} if route == "space-display-state" else {})
    if route == "space-display-state-header":
        client.credentials(HTTP_AUTHORIZATION=f"Display {token}")
        bad.credentials(HTTP_AUTHORIZATION="Display wrong-g6-secret")
    def check(response, missing=None):
        screen.refresh_from_db()
        assert screen.last_seen_at == now
        assert response.data["state"] == "paired"
        assert response.data["space"]["slug"] == space.slug
        assert response.data["config"]["name"] == "G6 panel screen"
        assert response.data["announcement"] == "G6 public announcement"
        assert response.data["here_now"]["total"] == 1
        if missing == "machines":
            assert response.data["machines"] is None
        else:
            assert response.data["machines"]["items"] == [{"name": "G6 public machine", "type": "G6 machine type", "status": "free"}]
        if missing == "events":
            assert response.data["calendar"] is None
        else:
            assert [(r["token"], r["title"]) for r in response.data["calendar"]["events"]] == [(str(event.public_token), event.title)]
    fallback = key in {"machines", "events"}
    cycle(space, key, lambda: client.get(url), check, off=(200, None) if fallback else (404, "not_found"),
          off_check=(lambda response: check(response, key)) if fallback else None,
          # A fallback GET can update its heartbeat, an intended protocol effect.
          off_mutates=fallback, probes=[hidden(lambda: bad.get(bad_url))])


@pytest.mark.parametrize("key", ["presence", "presence.public_display"])
@pytest.mark.parametrize("native", [False, True], ids=["browser", "native-carrier"])
def test_unclaimed_display_registration_has_no_tenant_gate_and_persists_only_digest(key, native, monkeypatch):
    space, actor, carrier, stranger, _foreign = world(native)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    client = carrier if native else APIClient()
    url = reverse("space-display-register")
    def check(response):
        row = DisplayScreen.objects.get()
        assert row.makerspace_id is None and row.token_digest == digest(response.data["token"])
        assert row.token_digest != response.data["token"]
        assert row.pairing_code == response.data["code"] and len(row.pairing_code) == 6
        assert row.code_expires_at == now + timedelta(minutes=30)
        for route in ("space-display-state-header", "space-display-state"):
            kwargs = {"token": response.data["token"]} if route == "space-display-state" else {}
            poll = APIClient()
            if route == "space-display-state-header":
                poll.credentials(HTTP_AUTHORIZATION="Display " + response.data["token"])
            reply = poll.get(reverse(route, kwargs=kwargs))
            assert reply.status_code == 200
            assert reply.data == {"state": "unclaimed", "code": row.pairing_code,
                                  "code_expires_at": row.code_expires_at.isoformat()}
    cycle(space, key, lambda: send(client, "post", url), check, on=(201, None),
          off=(201, None), off_check=check, off_mutates=True)
