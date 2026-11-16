"""Personal inbox/preferences preserve addressed rows on browser and native sessions."""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.audit.models import AuditLog
from apps.notifications.models_inbox import MemberNotificationPreference, NotificationInboxRow
from tests.accounts.account_factories import device_grant
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for, response_pair
from tests.payments.account_helpers import make_payer
from tests.payments.switch_helpers_cx11b_p2 import no_domain_writes, route_cycle
from tests.return_helpers import authenticated_client

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications]


def personal_client(user, space, native):
    if not native:
        return authenticated_client(user)
    from apps.makerspaces.public_profile_handles import ensure_default_handle
    ensure_default_handle(user)
    grant = device_grant(user)
    access, _refresh, _family = issue_device_token_pair(user, grant)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}", HTTP_X_MAKERSPACE_ID=str(space.pk))
    return client


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["notifications", "notifications.member_inbox", "notifications.member_preferences",
                                 "notifications.inbox_snooze"])
def test_personal_object_switch_restores_same_addressed_row_and_saved_opt_out(native, key):
    space = live_space("p2-personal", MODULE_KEYS)
    person = make_payer("p2-personal-owner", space)
    client = personal_client(person, space, native)
    row = NotificationInboxRow.objects.create(makerspace=space, user=person, feature="hardware_requests",
        event="issued", event_key=uuid4(), audience="member", title="Retained notice", summary="Private evidence notice")
    preference = MemberNotificationPreference.objects.create(makerspace=space, user=person,
        feature="hardware_requests", channel="email", enabled=False)
    url, method, body = f"/api/v1/notifications/inbox/{space.pk}", "get", None
    if key == "notifications.member_preferences":
        url = f"/api/v1/notifications/preferences/{space.pk}"
    elif key == "notifications.inbox_snooze":
        url, method = url + f"/{row.pk}/snooze", "post"
        body = {"until": (timezone.now() + timedelta(hours=2)).isoformat()}
    before = AuditLog.objects.filter(makerspace=space, action="notification.inbox_snoozed").count()
    def check(response):
        if key == "notifications.member_preferences":
            cells = [cell for cell in response.data["cells"]
                     if (cell["feature"], cell["channel"]) == ("hardware_requests", "email")]
            assert len(cells) == 1 and cells[0]["enabled"] is False
        elif key == "notifications.inbox_snooze":
            row.refresh_from_db()
            assert row.snoozed_until == datetime.fromisoformat(body["until"])
            assert response.data["id"] == row.pk
            assert datetime.fromisoformat(response.data["snoozed_until"].replace("Z", "+00:00")) == row.snoozed_until
            assert AuditLog.objects.filter(makerspace=space, action="notification.inbox_snoozed").count() == before + 1
        else:
            assert response.data["count"] == 1
            assert [(item["id"], item["title"], item["summary"]) for item in response.data["results"]] == [
                (row.pk, "Retained notice", "Private evidence notice")]
    route_cycle(space, client, {"notice": row, "preference": preference}, key, url, method=method, body=body,
        check=check,
        off=(404, "module_disabled" if key == "notifications" else "not_found" if key.endswith("snooze") else "feature_disabled"))
    assert MemberNotificationPreference.objects.get(pk=preference.pk).enabled is False


@pytest.mark.parametrize("key", ["notifications.web_push", "notifications"])
def test_browser_push_config_restores_retained_platform_configuration_and_refuses_native(key):
    from apps.integrations.models_push import PlatformPushSettings
    from tests.accounts.account_factories import make_staff
    from tests.notifications.test_browser_firebase_config import config, credential
    space = live_space("p2-web-push", MODULE_KEYS)
    actor = make_staff(space, username="p2-web-push-staff", access_status="active")
    row = PlatformPushSettings.objects.create(pk=1, firebase_web_config=config())
    row.set_fcm_service_account(credential("example-project"))
    row.save(update_fields=["fcm_service_account"])
    url = f"/api/v1/notifications/browser-firebase/{space.pk}/config"
    native = client_for(actor, space, True)
    with no_domain_writes():
        assert response_pair(native.get(url)) == (403, "permission_denied")
    route_cycle(space, client_for(actor, space, False), {"platform_config": row}, key, url,
        off=(404, "module_disabled" if key == "notifications" else "not_found"),
        check=lambda response: check_configured(response, config()))


def check_configured(response, public_config):
    assert response.data == {"configured": True, "config": public_config}
    assert "PRIVATE KEY" not in str(response.data)
    assert response["Cache-Control"] == "no-store"
