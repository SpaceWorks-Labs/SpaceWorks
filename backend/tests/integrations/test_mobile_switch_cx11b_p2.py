"""Native push registration is device-only and survives switch cycles without sending push."""
import hashlib
import hmac

import pytest

from apps.accounts.models import DeviceGrant
from apps.audit.models import AuditLog
from apps.integrations.models_push import PushDevice
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.notifications.test_object_switches_cx11b_p2 import personal_client
from tests.payments.account_helpers import make_payer
from tests.payments.switch_helpers_cx11b_p2 import route_cycle, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_mobile, pytest.mark.area_notifications]


@pytest.mark.parametrize("key", ["mobile.push", "mobile"])
def test_native_registration_restores_same_encrypted_token_and_browser_cannot_register(settings, key):
    settings.PUSH_TOKEN_HMAC_KEY = "p" * 64
    space = live_space("p2-mobile", MODULE_KEYS)
    person = make_payer("p2-mobile-owner", space)
    from apps.makerspaces.public_profile_handles import ensure_default_handle
    ensure_default_handle(person)
    client = personal_client(person, space, True)
    body = {"token": "p2_test_device_token_1234567890", "provider": "fcm", "environment": "development"}
    url = "/api/v1/integrations/push/devices"
    grant = DeviceGrant.objects.get(user=person)
    fingerprint = hmac.new(settings.PUSH_TOKEN_HMAC_KEY.encode(),
        "{provider}\0{environment}\0{token}".format(**body).encode(), hashlib.sha256).hexdigest()
    audits = AuditLog.objects.filter(makerspace=space, action="push.device_registered")
    audit_before = audits.count()
    first = client.post(url, body, format="json")
    assert response_pair(first) == (201, None), first.data
    row = PushDevice.objects.get(pk=first.data["id"])

    def check_registration(response):
        assert response.data["id"] == row.pk
        assert PushDevice.objects.count() == 1
        persisted = PushDevice.objects.get(pk=row.pk)
        assert persisted.get_token() == body["token"]
        assert body["token"] not in persisted.token_ciphertext
        assert persisted.token_fingerprint == fingerprint
        assert persisted.user_id == person.pk
        assert persisted.makerspace_id == space.pk
        assert persisted.device_grant_id == grant.pk
        assert persisted.provider == body["provider"]
        assert persisted.environment == body["environment"]
        assert persisted.active is True
        assert persisted.invalidated_at is None
        assert audits.count() == audit_before + 1
        event = audits.latest("pk")
        assert event.actor_id == person.pk
        assert event.target_type == "integrations.pushdevice"
        assert event.target_id == str(row.pk)
        assert event.meta == {"provider": body["provider"], "environment": body["environment"]}

    check_registration(first)
    audit_before = audits.count()
    route_cycle(space, client, {"push": row}, key, url, method="post", body=body,
        off=(404, "feature_disabled"), check=check_registration)
    original = switch(space, "notifications")
    audit_before = audits.count()
    independent = client.post(url, body, format="json")
    assert response_pair(independent) == (200, None), independent.data
    check_registration(independent)
    switch(space, "notifications", original=original)
    refused = personal_client(person, space, False).post(url, body, format="json")
    assert response_pair(refused) == (403, "permission_denied")
