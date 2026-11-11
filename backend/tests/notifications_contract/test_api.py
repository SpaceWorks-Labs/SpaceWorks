import pytest
from rest_framework.test import APIClient

from tests.accounts.reauth_helpers import reauthenticate
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def client(user):
    result = APIClient()
    result.force_authenticate(user)
    return result


def stepped_up(user):
    """Credential writes need the real session-bound password step-up first."""
    result = APIClient()
    reauthenticate(result, user)
    return result


def base(space):
    return f"/api/v1/integrations/makerspace/{space.pk}"


@pytest.mark.parametrize("role", ["space_manager", "inventory_manager", "machine_manager", "event_manager", "booking_manager", "handover", "member"])
def test_only_space_manager_can_configure_channels(role):
    space = make_space("contract-api-" + role)
    user = make_member("contract-" + role, space, membership_role=role)
    # Staff roles live on the staff-TRACK row; the member role on the community row.
    from apps.makerspaces.models import MakerspaceMembership
    track = MakerspaceMembership.Track.STAFF if role != "member" else MakerspaceMembership.Track.COMMUNITY
    membership = MakerspaceMembership.track_manager(track).get(user=user, makerspace=space)
    membership.assigned_role = space.roles.get(slug=role)
    if role == "member":
        membership.role = "custom"
    membership.save(update_fields=["role", "assigned_role"])
    api = stepped_up(user) if role == "space_manager" else client(user)
    response = api.patch(base(space) + "/channels/whatsapp", {
        "provider": "meta", "enabled": True, "integration_identity": "123",
        "credentials": {"app_id": "1", "app_secret": "secret", "business_account_id": "2",
                        "phone_number_id": "123", "access_token": "token", "webhook_verify_token": "verify"},
    }, format="json")
    assert response.status_code == (200 if role == "space_manager" else 403)


def test_credentials_and_destinations_never_appear_in_http(contract):
    c = contract
    sm = make_member("contract-sm", c.space)
    response = stepped_up(sm).patch(base(c.space) + "/channels/telegram", {
        "credentials": {"bot_token": "TOP-SECRET"},
    }, format="json")
    assert response.status_code == 200
    assert "TOP-SECRET" not in str(response.data) and response.data["credentials_set"]
    listed = client(c.user).get(base(c.space) + "/personal/endpoints")
    assert listed.status_code == 200
    assert "destination" not in listed.data["results"][0] and "provider_subject" not in listed.data["results"][0]


def test_personal_endpoint_id_is_never_a_browser_input(contract):
    c = contract
    response = client(c.user).post(base(c.space) + "/personal/endpoints/start", {
        "channel": "telegram", "consent": True, "consent_version": "v1", "destination": "somebody-else",
    }, format="json")
    assert response.status_code == 400


def test_members_can_choose_multiple_channels_and_revoke_only_their_endpoint(contract):
    c = contract
    api = client(c.user)
    response = api.put(base(c.space) + "/personal/preferences", {"preferences": [{
        "category": "hardware_requests", "channels": ["telegram", "email"], "email_fallback": False,
    }]}, format="json")
    assert response.status_code == 200
    preference = next(p for p in response.data["preferences"] if p["category"] == "hardware_requests")
    assert preference["channels"] == ["telegram", "email"]
    other = make_member("other-contract-member", c.space, membership_role="member")
    assert client(other).delete(base(c.space) + f"/personal/endpoints/{c.endpoint.pk}").status_code == 404
    assert api.delete(base(c.space) + f"/personal/endpoints/{c.endpoint.pk}").status_code == 200


def test_cross_tenant_access_is_refused(contract):
    other = make_space("contract-cross-tenant")
    assert client(contract.user).get(base(other) + "/personal/endpoints").status_code == 403
    assert client(contract.user).patch(base(other) + "/channels/telegram", {}, format="json").status_code == 403


def test_reinstall_rotates_generation_without_reactivating_consent(contract):
    c = contract
    sm = make_member("rotate-contract-sm", c.space)
    response = stepped_up(sm).patch(base(c.space) + "/channels/telegram", {
        "credentials": {"bot_token": "new-secret"},
    }, format="json")
    assert response.status_code == 200 and response.data["generation"] == c.config.generation + 1
    c.endpoint.refresh_from_db()
    assert c.endpoint.integration_generation == c.config.generation


def test_chat_digest_and_duplicate_channels_are_rejected(contract):
    response = client(contract.user).put(base(contract.space) + "/personal/preferences", {"preferences": [{
        "category": "hardware_requests", "channels": ["telegram"], "daily_digest": True,
    }]}, format="json")
    assert response.status_code == 400


def test_delivery_metadata_is_personal_except_for_space_manager(contract):
    from apps.integrations.notification_delivery import ensure_deliveries
    c = contract
    envelope = c.envelope()
    ensure_deliveries(envelope)
    count = envelope.deliveries.count()
    assert count > 0
    other = make_member("contract-log-manager", c.space, membership_role="inventory_manager")
    sm = make_member("contract-log-sm", c.space)
    assert client(other).get(base(c.space) + "/personal/deliveries").data["count"] == 0
    for user in (c.user, sm):
        response = client(user).get(base(c.space) + "/personal/deliveries")
        assert response.status_code == 200 and response.data["count"] == count
        assert all("message_body" not in row and "destination" not in row for row in response.data["results"])


@pytest.mark.parametrize("role", ["inventory_manager", "machine_manager", "event_manager", "booking_manager", "handover", "member"])
def test_non_space_managers_cannot_test_delivery(contract, role):
    c = contract
    user = make_member("contract-test-" + role, c.space, membership_role=role)
    response = client(user).post(base(c.space) + "/channels-test", {
        "channel": "telegram", "endpoint_id": c.endpoint.pk,
    }, format="json")
    assert response.status_code == 403


def test_http_start_and_provider_verified_completion(contract):
    from urllib.parse import parse_qs, urlsplit
    from apps.integrations.notification_providers import CallbackEvent, EndpointProof
    from apps.integrations.models_endpoints import NotificationEndpoint
    c = contract
    api = client(c.user)
    response = api.post(base(c.space) + "/personal/endpoints/start", {
        "channel": "telegram", "consent": True, "consent_version": "v1",
    }, format="json")
    assert response.status_code == 201
    assert NotificationEndpoint.objects.filter(user=c.user).count() == 1
    code = parse_qs(urlsplit(response.data["connect_url"]).query)["code"][0]
    c.fake.callback = CallbackEvent(proof=EndpointProof(code, "private-proof", c.config.integration_identity,
                                                      "new-subject", private=True))
    url = base(c.space) + f"/personal/challenges/{response.data['challenge_id']}/verify"
    verified = api.post(url, {}, format="json")
    assert verified.status_code == 200 and verified.data["verification_state"] == "verified"
    assert api.post(url, {}, format="json").data["id"] == verified.data["id"]
    assert NotificationEndpoint.objects.filter(user=c.user, revoked_at=None).count() == 1
