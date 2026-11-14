"""API-client quota counts live credentials; approval and reactivation are creators."""
import pytest
from django.contrib import admin
from django.db import connection
from django.urls import reverse

from apps.apiclients import key_request_decisions
from apps.apiclients.models import ApiClient, ApiKeyRequest
from apps.audit.models import AuditLog
from tests.inventory.test_alternative_creators_cx7_p4a import race
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.admin_capacity_helpers_cx7 import bound_form
from tests.r2_superadmin_local.helpers import superadmin
from tests.return_helpers import authenticated_client, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_auth, pytest.mark.area_platform]


def world(settings):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-key-life")
    space.resource_limit_overrides = {"api_clients": 1}
    space.save(update_fields=["resource_limit_overrides"])
    return space


def inactive(space, label):
    row, _ = ApiClient.issue(label=label, makerspace=space, scopes=["public:read"],
                            allowed_origins=["https://example.test"])
    row.is_active = False
    row.save(update_fields=["is_active"])
    return row


def approval(space, index):
    return ApiKeyRequest.objects.create(makerspace=space, label=f"Approval {index}",
                                        allowed_origins=["https://example.test"])


def snapshot():
    return {model.__name__: list(model.objects.order_by("pk").values())
            for model in (ApiClient, ApiKeyRequest, AuditLog)}


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_reactivation_max_next_and_rotation_revocation_deletion_at_capacity(surface, settings, monkeypatch):
    space = world(settings)
    caller = callers(space, surface, settings, monkeypatch)[0]
    if surface != "browser":
        from apps.accounts.mfa_crypto import totp
        from apps.accounts.models_mfa import UserMFA
        from apps.makerspaces.secrets import decrypt_value
        from django.utils import timezone
        factor = UserMFA.objects.get(user__username=f"{space.slug}-{surface}")
        code = totp(decrypt_value(factor.secret), int(timezone.now().timestamp() // 30) + 1)
        proof = caller.post("/api/v1/auth/reauth", {"password": "strong-device-password", "code": code}, format="json")
        assert proof.status_code == 200, proof.data
        assert proof.data["verified"] is True
    first, second = inactive(space, "First"), inactive(space, "Second")
    url = reverse("admin-api-client", args=[first.pk])
    assert caller.patch(url, {"is_active": True}, format="json").status_code == 200
    before = snapshot()
    refused = caller.patch(reverse("admin-api-client", args=[second.pk]), {"is_active": True}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "limit_reached")
    assert snapshot() == before
    old_secret = first.get_secret()
    rotated = caller.post(reverse("admin-api-client-rotate-secret", args=[first.pk]), {}, format="json")
    assert rotated.status_code == 200
    first.refresh_from_db()
    assert first.get_secret() != old_secret
    assert ApiClient.objects.filter(makerspace=space, is_active=True).count() == 1
    assert caller.patch(url, {"is_active": False}, format="json").status_code == 200
    assert caller.patch(reverse("admin-api-client", args=[second.pk]), {"is_active": True}, format="json").status_code == 200
    assert caller.delete(url).status_code == 204
    assert ApiClient.objects.filter(makerspace=space).count() == 1


@pytest.mark.parametrize("surface", ["browser", "control"])
def test_key_approval_max_next_preserves_pending_request_and_audit(surface, settings, monkeypatch):
    space = world(settings)
    actor = superadmin("p4a-approve-root")
    rows = [approval(space, index) for index in range(2)]
    monkeypatch.setattr(key_request_decisions, "notify_api_key_request_resolved", lambda row: None)
    if surface == "browser":
        caller = authenticated_client(actor)
        assert caller.post(reverse("admin-platform-api-key-request-approve", args=[rows[0].pk]), {}, format="json").status_code == 200
        before = snapshot()
        refused = caller.post(reverse("admin-platform-api-key-request-approve", args=[rows[1].pk]), {}, format="json")
        assert (refused.status_code, refused.json()["code"]) == (400, "limit_reached")
    else:
        model_admin = admin.site._registry[ApiKeyRequest]
        _, _, request, _ = bound_form(rows[0], actor, instance=rows[0])
        model_admin.approve_and_issue(request, ApiKeyRequest.objects.filter(pk=rows[0].pk))
        before = snapshot()
        model_admin.approve_and_issue(request, ApiKeyRequest.objects.filter(pk=rows[1].pk))
        assert any("limit_reached" in str(message) for message in request._messages)
    assert snapshot() == before
    rows[1].refresh_from_db()
    assert (rows[1].status, rows[1].resolved_at, rows[1].resolved_by_id) == ("pending", None, None)
    assert ApiClient.objects.filter(makerspace=space, is_active=True).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["approval", "reactivation", "mixed"])
def test_credential_creators_racing_at_last_slot_admit_one(kind, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space = world(settings)
    actor = superadmin("p4a-key-race-root")
    pair = [authenticated_client(actor), authenticated_client(actor)]
    monkeypatch.setattr(key_request_decisions, "notify_api_key_request_resolved", lambda row: None)
    commands = []
    for index in range(2):
        if kind == "reactivation" or (kind == "mixed" and index == 1):
            row = inactive(space, f"Dormant {index}")
            commands.append(("patch", reverse("admin-api-client", args=[row.pk]), {"is_active": True}, 200))
        else:
            row = approval(space, index)
            commands.append(("post", reverse("admin-platform-api-key-request-approve", args=[row.pk]), {}, 200))
    results = race(pair, commands)
    assert sorted(status for status, _ in results) == [200, 400]
    assert [body["code"] for status, body in results if status == 400] == ["limit_reached"]
    assert ApiClient.objects.filter(makerspace=space, is_active=True).count() == 1


def test_platform_native_credentials_are_routeless(settings, monkeypatch):
    """A platform approval cannot be reached by minting a native platform grant."""
    from apps.accounts.models import DeviceGrant
    from rest_framework.test import APIClient
    from tests.accounts.native_helpers_m1d import attested_login
    from tests.return_helpers import make_user
    actor = make_user("p4a-native-platform-root", role="superadmin", password="strong-device-password")
    response, _ = attested_login(APIClient(), actor, settings, monkeypatch)
    assert (response.status_code, response.json()["code"]) == (401, "authentication_failed")
    assert DeviceGrant.objects.filter(user=actor).count() == 0


def test_control_import_approval_add_is_routeless(client):
    from apps.apiclients.models import ApiClientImportApproval
    from django.test import RequestFactory
    from tests.accounts.reauth_helpers import force_recent_control_login
    actor = superadmin("p4a-import-approval-root")
    force_recent_control_login(client, actor)
    request = RequestFactory().get("/control/")
    request.user = actor
    registered = admin.site._registry[ApiClientImportApproval]
    assert registered.has_add_permission(request) is False
    before = ApiClientImportApproval.objects.count()
    url = reverse("admin:apiclients_apiclientimportapproval_add")
    assert client.get(url).status_code == 403
    assert client.post(url, {}).status_code == 403
    assert ApiClientImportApproval.objects.count() == before
