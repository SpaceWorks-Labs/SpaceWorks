"""#190 follow-up: mobile app identities from the web console. Local only."""

import pytest
from django.core.cache import cache

from apps.accounts.models_devices import NativeAppRegistration
from apps.audit.models import AuditLog
from tests.r2_superadmin_local.helpers import api, manager, space, superadmin

pytestmark = pytest.mark.django_db
A = "/api/v1/admin/platform/native-apps"
DIGEST = "AB:" * 31 + "AB"
BODY = {"app_id": "org.spaceworks.app", "platform": "android", "environment": "production",
        "verifier_config_key": "default", "signing_identities": [DIGEST], "status": "pending"}


@pytest.fixture
def root():
    cache.clear()
    return superadmin("apps-root")


def test_staff_are_refused(root):
    assert api(manager(space("apps-staff"))).get(A).status_code in {401, 403}


def test_register_approve_and_revoke_through_the_control_form(root):
    client = api(root)
    created = client.post(A, BODY, format="json")
    assert created.status_code == 201, created.json()
    pk = created.json()["id"]
    approved = client.patch(f"{A}/{pk}", {"status": "approved"}, format="json")
    assert approved.status_code == 200 and approved.json()["approved_by"] == root.username
    revoked = client.patch(f"{A}/{pk}", {"status": "revoked"}, format="json")
    assert revoked.json()["status"] == "revoked" and revoked.json()["revoked_at"]
    assert AuditLog.objects.filter(action="native_app.revoked").exists()
    rows = AuditLog.objects.filter(action="native_app.registration_updated", meta__via="console").order_by("pk")
    assert [row.meta["created"] for row in rows] == [True, False, False]
    assert client.get(A).json()["count"] == 1
    assert client.delete(f"{A}/{pk}").status_code == 405


def test_the_control_validation_applies(root):
    bad = api(root).post(A, {**BODY, "app_id": "not a package"}, format="json")
    assert bad.status_code == 400 and "app_id" in bad.json()
    assert not NativeAppRegistration.objects.exists()


def test_the_parity_rows_moved_to_web_and_the_kept_host_rows_say_why():
    from config.control_parity import PARITY
    for key in ("integrations.platformsmssettings", "integrations.platformpushsettings",
                "integrations.platformwhatsappsettings", "accounts.platformattestationsettings",
                "accounts.nativeappregistration", "accounts.platformloginmethods", "view:makerspaces_makerspace_keys",
                "view:makerspaces_makerspace_capability_purge", "keys:reencrypt", "keys:purge", "integrations.chattemplate"):
        assert PARITY[key].kind == "web", key
    for key in ("keys:rotate_platform", "keys:rotate_server", "keys:reencrypt_all", "view:control-rls", "axes.accessattempt"):
        assert PARITY[key].kind == "host", key
