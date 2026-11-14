"""Public presence projections require no membership: anonymous is a valid no-standing caller."""
from urllib.parse import urlsplit

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.makerspaces.models_account_profile import AccountProfile
from apps.presence.models_anthias import SpaceNowConfig
from tests.notifications.routes_support_cx11b_g6 import cycle, world
from tests.presence.routes_support_cx11b_g6 import seed
from tests.presence.test_related_routes_cx11b_g6 import neighbours

pytestmark = [pytest.mark.django_db, pytest.mark.area_presence]
CASES = [("public-presence-now", "presence"), ("public-presence-now", "events"),
         ("public-presence-here-now", "presence"), ("public-machines-now", "machines"),
         ("public-machines-now", "presence"), ("public-presence-now-config", "presence")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("route,key", CASES)
def test_public_read_returns_seeded_projection_without_tenant_standing(route, key, native, settings):
    settings.PUBLIC_APP_BASE_URL = "https://testserver"
    space, actor, client, stranger, foreign = world(native)
    actor.display_name = "G6 public maker"
    actor.save(update_fields=["display_name"])
    row, preference, project = seed(space, actor)
    event, booking, machine_session = neighbours(space, actor, row)
    AccountProfile.objects.filter(user=actor).update(public_visible=True, public_consented_at=timezone.now())
    config = SpaceNowConfig.objects.create(makerspace=space, sections=["opening_hours"], privacy="counts", refresh_seconds=60)
    url = reverse(route, kwargs={"makerspace_slug": space.slug})
    anon = APIClient()
    # 303b: open-web profile reads validate the request host. Native setup creates
    # a live handle, so anonymous Here-now cards reach that check too.
    for caller in (client, anon, foreign):
        caller.defaults["HTTP_HOST"] = urlsplit(settings.PUBLIC_APP_BASE_URL).netloc
    fallback = (route == "public-presence-now" and key == "events" or
                route == "public-machines-now" and key == "presence" or route == "public-presence-now-config")
    def check(response, disabled=False):
        if route == "public-presence-now":
            expected = {"display_name": "G6 public maker", "status": "attending_event", "since": row.started_at.isoformat()}
            if not disabled:
                expected["event_title"] = event.title
            assert response.data == [expected]
        elif route == "public-presence-here-now":
            assert response.data["total"] == 1
            assert response.data["others_count"] == 1 and response.data["people"] == []  # counts privacy
        elif route == "public-machines-now":
            assert response.data == {"in_use": 0, "free": 1, "out_of_service": 0,
                "items": [{"name": "G6 public machine", "type": "G6 machine type", "status": "free"}]}
        else:
            assert response.data == {"sections": ["opening_hours"], "privacy": "counts", "refresh_seconds": 60}
    # Public/anonymous reads share the projection; no actor's private rows are exposed.
    off = (200, None) if fallback else (404, "not_found")
    cycle(space, key, lambda: client.get(url), check, off=off,
          off_check=(lambda response: check(response, route == "public-presence-now")) if fallback else None,
          probes=[(lambda: anon.get(url), (200, None), off), (lambda: foreign.get(url), (403, "permission_denied") if native else (200, None),
                   (403, "permission_denied") if native else off)])
