from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations.notification_slack_oauth import state_for
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db


def test_authenticated_return_recovers_challenge_from_signed_state_without_browser_storage(world):
    config = world.config()
    world.space.enabled_modules = sorted(set(world.space.enabled_modules) | {"discord", "notifications"})
    world.space.save(update_fields=["enabled_modules"])
    row, code = world.challenge(config)
    url = f"/api/v1/integrations/makerspace/{world.space.pk}/personal/endpoints"
    response = world.client(world.owner, jwt=True).get(url, {"oauth_state": state_for(row, code)})
    assert response.status_code == 200, response.data
    assert response.data["oauth_return"]["challenge_id"] == row.pk
    row.refresh_from_db()
    assert not row.consumed_at  # Lookup never exchanges the code or establishes identity.


@pytest.mark.parametrize("failure", ["user", "tenant", "signature", "expiry", "rotation", "disabled", "purpose"])
def test_return_lookup_never_exposes_an_unbound_challenge(world, failure):
    config = world.config()
    world.space.enabled_modules = sorted(set(world.space.enabled_modules) | {"discord", "notifications"})
    world.space.save(update_fields=["enabled_modules"])
    row, code = world.challenge(config)
    state = state_for(row, code, purpose="install" if failure == "purpose" else "link")
    actor, space = world.owner, world.space
    if failure == "user":
        actor = world.other
    elif failure == "tenant":
        space = Makerspace.objects.create(name="Other", slug="review4-oauth-other")
        world.person("other-manager", "space_manager", tenant=space)
    elif failure == "signature":
        state += "tamper"
    elif failure == "expiry":
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save()
    elif failure == "rotation":
        config.generation += 1
        config.save()
    elif failure == "disabled":
        config.personal_enabled = False
        config.save()
    response = world.client(actor).get(f"/api/v1/integrations/makerspace/{space.pk}/personal/endpoints", {"oauth_state": state})
    assert response.status_code in {400, 403, 404}, response.data
    assert "oauth_return" not in response.data
