import pytest

from apps.makerspaces.models import MakerspaceMembership
from tests.hardware_requests.test_kiosk_online import make_staff
from tests.hardware_requests.replay_helpers import replay_env  # noqa: F401 -- pytest fixture
from tests.hardware_requests.recovery_helpers import failed_issue, recovery_url, resolve, staff_client
from tests.hardware_requests.test_kiosk_online import kiosk_space

pytestmark = pytest.mark.django_db


def test_list_filters_paginate_and_do_not_return_channel_or_payload_secrets(replay_env, settings):
    env = replay_env
    one, two = failed_issue(env), failed_issue(env)
    client = staff_client(env.user)
    assert resolve(client, one).status_code == 200
    url = recovery_url("list", makerspace_id=env.space.pk)
    assert client.get(url).data["count"] == 1
    assert client.get(url, {"resolution": "resolved"}).data["results"][0]["id"] == str(one.pk)
    assert client.get(url, {"resolution": "all"}).data["count"] == 2
    assert client.get(url, {"resolution": "unknown"}).status_code == 400
    assert client.get(url, {"state": "prepared"}).status_code == 400
    data = client.get(recovery_url("detail", pk=two.pk)).data
    assert data["station_name"] == env.station.name and data["can_view_evidence"]
    assert not {"payload", "payload_fingerprint", "object_key", "pin", "public_token", "lease_token"} & set(data)


def test_cross_tenant_detail_resolve_and_origin_are_refused(replay_env):
    env = replay_env
    row = failed_issue(env)
    foreign = kiosk_space("recovery-foreign")
    client = staff_client(make_staff(foreign))
    assert client.get(recovery_url("list", makerspace_id=env.space.pk)).data["count"] == 0
    assert client.get(recovery_url("detail", pk=row.pk)).status_code == 404
    assert resolve(client, row).status_code == 404
    # Same user has authority, but a foreign tenant frontend must not route it.
    foreign.frontend_domain = "foreign.example.test"
    foreign.frontend_domain_status = "verified"
    foreign.save(update_fields=["frontend_domain", "frontend_domain_status"])
    own = staff_client(env.user)
    for name, kwargs in (("list", {"makerspace_id": env.space.pk}), ("detail", {"pk": row.pk})):
        assert own.get(recovery_url(name, **kwargs), HTTP_ORIGIN="https://foreign.example.test").status_code == 403
    assert own.post(recovery_url("resolve", pk=row.pk), {"resolution_code": "acknowledged_no_change"},
                    format="json", HTTP_ORIGIN="https://foreign.example.test").status_code == 403


@pytest.mark.parametrize("change", ["suspended", "restricted", "membership", "password", "inactive"])
def test_revoked_current_authority_cannot_review(replay_env, change):
    env = replay_env
    row = failed_issue(env)
    if change == "membership":
        MakerspaceMembership.objects.filter(user=env.user).update(status="revoked")
    else:
        if change in ("suspended", "restricted"):
            env.user.access_status = change
        elif change == "password":
            env.user.must_change_password = True
        else:
            env.user.is_active = False
        env.user.save()
    response = resolve(staff_client(env.user), row)
    assert response.status_code in (403, 404)
    row.refresh_from_db()
    assert row.resolution_code is None


def test_historical_review_survives_kiosk_disable(replay_env):
    env = replay_env
    row = failed_issue(env)
    env.space.enabled_features = [key for key in env.space.enabled_features if key != "inventory.kiosk"]
    env.space.save(update_fields=["enabled_features"])
    assert resolve(staff_client(env.user), row).status_code == 200
