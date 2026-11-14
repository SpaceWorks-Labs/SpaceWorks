"""Admission HTTP variants retain real native attestation, MFA and session reauthentication."""
import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.mfa_crypto import totp
from apps.accounts.models_mfa import UserMFA
from apps.makerspaces.limits_usage import _COUNTERS
from apps.makerspaces.secrets import decrypt_value
from tests.admin_api.test_staff_roles_api import client_for
from tests.machines.test_intake_limits_cx7_p4b import member_client
from tests.makerspaces.test_admission_limits_cx7_p4b import member_world, staff_world, snapshot
from tests.makerspaces.test_daily_delivery_creator_races_cx7 import race
from tests.makerspaces.test_membership_j1 import member_role
from tests.shop.test_native_shop_limits_cx7 import native_staff_client

pytestmark = [pytest.mark.django_db, pytest.mark.area_membership, pytest.mark.area_staff_admin, pytest.mark.area_mobile]
KINDS = ["open", "approval", "claim", "claim_legacy", "staff_grant"]


def staff_pair(space, actor, surface, settings, monkeypatch):
    if surface == "browser":
        settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]
        settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5000"]
        first = client_for(actor)
    else:
        first, actor = native_staff_client(space, surface, settings, monkeypatch)
        factor = UserMFA.objects.get(user=actor)
        code = totp(decrypt_value(factor.secret), int(timezone.now().timestamp() // 30) + 1)
        response = first.post("/api/v1/auth/reauth", {"password": "strong-device-password", "code": code}, format="json")
        assert response.status_code == 200
        assert response.json()["verified"] is True
    second = APIClient()
    second.credentials(**first._credentials)
    return [first, second]


def setup(kind, surface, settings, monkeypatch):
    if kind == "staff_grant":
        w = staff_world("grant", monkeypatch)
    else:
        w = member_world("claim" if kind.startswith("claim") else kind)
    space, actor, people, rows, _ = w
    if kind in {"staff_grant", "approval"}:
        pair = staff_pair(space, actor, surface, settings, monkeypatch)
    else:
        # Joining has no active community membership to select yet. These
        # account-owned routes resolve the target from their URL/invitation.
        pair = [member_client(person, surface, settings, monkeypatch) for person in people]
    key = "staff" if kind == "staff_grant" else "members"
    baseline = _COUNTERS[key](space)
    space.resource_limit_overrides = {key: baseline + 1}
    space.save(update_fields=["resource_limit_overrides"])

    def post(index):
        if kind == "staff_grant":
            url = f"/api/v1/admin/makerspaces/{space.pk}/staff-roles/"
            body = {"user_id": people[index].pk, "roles": ["inventory_manager"]}
        elif kind == "approval":
            url = reverse("admin-membership-request-approve", kwargs={"pk": rows[index].pk})
            body = {"role_id": member_role(space).pk}
        elif kind.startswith("claim"):
            route = "membership-invitation-claim-legacy" if kind == "claim_legacy" else "membership-invitation-claim"
            url, body = reverse(route, kwargs={"pk": rows[index].pk}), {}
        else:
            url, body = reverse("public-membership-request", kwargs={"makerspace_slug": space.slug}), {}
        return pair[index].post(url, body, format="json")
    return space, key, baseline, post


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_admission_http_max_next_exact_refusal_has_no_membership_or_proof_writes(kind, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, key, baseline, post = setup(kind, surface, settings, monkeypatch)
    assert post(0).status_code == (200 if kind in {"approval", "claim", "claim_legacy"} else 201)
    before = snapshot()
    refused = post(1)
    assert (refused.status_code, refused.json()["code"]) == ((409, "quota_exceeded") if key == "staff"
                                                          else (400, "limit_reached"))
    assert snapshot() == before
    assert _COUNTERS[key](space) == baseline + 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_admission_http_race_at_last_slot_admits_one(kind, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, key, baseline, post = setup(kind, surface, settings, monkeypatch)
    results = race(post)
    success = 200 if kind in {"approval", "claim", "claim_legacy"} else 201
    refused, code = (409, "quota_exceeded") if key == "staff" else (400, "limit_reached")
    assert sorted(response.status_code for response in results) == [success, refused]
    assert [response.json()["code"] for response in results if response.status_code == refused] == [code]
    assert _COUNTERS[key](space) == baseline + 1
