import pytest
from django.urls import reverse

from apps.accounts.authentication import _member_surface_path_allowed


@pytest.mark.parametrize("suffix", ["endpoints", "endpoints/start", "endpoints/7", "challenges/8/verify", "preferences", "deliveries"])
@pytest.mark.parametrize("slash", ["", "/"])
def test_exact_personal_routes_admit_member_sessions(suffix, slash):
    assert _member_surface_path_allowed(f"/api/v1/integrations/makerspace/12/personal/{suffix}{slash}")


@pytest.mark.parametrize("suffix", ["", "channels", "personal", "personal/endpoints/start/extra", "personal/endpoints/7/revoke",
    "personal/endpoints/nope", "personal/challenges/7", "personal/challenges/7/verify/extra", "personal/preferences/extra",
    "personal/deliveries/extra", "personal/endpoints//", "personal/endpoints/-1", "personal/endpoints/1x"])
def test_neighboring_staff_and_unknown_routes_stay_denied(suffix):
    assert not _member_surface_path_allowed(f"/api/v1/integrations/makerspace/12/{suffix}")


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["contract-endpoints", "contract-preferences", "contract-deliveries"])
def test_real_member_jwt_can_read_own_personal_routes(world, route):
    response = world.client(world.owner, jwt=True).get(reverse(route, kwargs={"makerspace_id": world.space.pk}))
    assert response.status_code == 200, response.data


@pytest.mark.django_db
def test_member_jwt_cannot_read_staff_channel_configuration(world):
    response = world.client(world.owner, jwt=True).get(reverse("contract-channels", kwargs={"makerspace_id": world.space.pk}))
    assert response.status_code == 403


@pytest.mark.django_db
def test_member_settings_remain_tenant_scoped(world):
    from apps.makerspaces.models import Makerspace
    foreign = Makerspace.objects.create(name="Foreign", slug="p3-foreign")
    response = world.client(world.owner, jwt=True).get(reverse("contract-endpoints", kwargs={"makerspace_id": foreign.pk}))
    assert response.status_code == 403


@pytest.mark.django_db
def test_member_jwt_can_start_verify_revoke_and_replace_own_preferences(world, monkeypatch):
    from types import SimpleNamespace
    from apps.integrations.notification_providers import CallbackEvent, EndpointProof, PROVIDERS
    config = world.config("telegram")
    state = {}
    def start(row, code):
        state["code"] = code
        return {"instructions": "Reply to connect"}
    fake = SimpleNamespace(start_challenge=start, verify_callback=lambda _: CallbackEvent(
        proof=EndpointProof(state["code"], "private-destination", config.integration_identity, "private-subject", private=True)))
    monkeypatch.setitem(PROVIDERS, ("telegram", "telegram"), lambda _: fake)
    client = world.client(world.owner, jwt=True)
    response = client.post(reverse("contract-endpoint-start", kwargs={"makerspace_id": world.space.pk}),
        {"channel": "telegram", "consent": True, "consent_version": "v1"}, format="json")
    assert response.status_code == 201, response.data
    response = client.post(reverse("contract-endpoint-verify", kwargs={"makerspace_id": world.space.pk,
        "challenge_id": response.data["challenge_id"]}), {}, format="json")
    assert response.status_code == 200, response.data
    endpoint_id = response.data["id"]
    assert client.put(reverse("contract-preferences", kwargs={"makerspace_id": world.space.pk}),
                      {"preferences": []}, format="json").status_code == 200
    endpoint_url = reverse("contract-endpoint-revoke", kwargs={"makerspace_id": world.space.pk, "pk": endpoint_id})
    assert world.client(world.other, jwt=True).delete(endpoint_url).status_code == 404
    assert client.delete(endpoint_url).status_code == 200
