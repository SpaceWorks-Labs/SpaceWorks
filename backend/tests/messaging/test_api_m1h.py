from unittest.mock import patch

import pytest
from django.contrib import admin
from django.urls import reverse

from apps.accounts.models import User
from apps.integrations.admin_messaging import PlatformWhatsAppSettingsForm
from apps.integrations.admin_sms import PlatformSmsSettingsForm
from apps.integrations.models import MakerspaceMessagingSettings, PlatformWhatsAppSettings
from tests.accounts.reauth_helpers import reauthenticate
from tests.messaging.canonical_helpers import OWN_SMS, platform_sms, sms_channel

pytestmark = pytest.mark.django_db


def test_settings_secrets_are_write_only_and_reauthentication_is_required(space, manager, client):
    client.force_authenticate(manager)
    url = reverse("messaging-settings", kwargs={"makerspace_id": space.pk})
    response = client.patch(url, {"sms_auth_token": "hidden"}, format="json")
    assert response.status_code in {401, 403}
    with patch("apps.integrations.messaging.views_settings.require_recent_reauth"):
        response = client.patch(url, {"sms_auth_token": "hidden"}, format="json")
    # D1: the duplicate legacy settings writer is retired in favour of channel settings.
    assert response.status_code == 410
    assert not MakerspaceMessagingSettings.objects.filter(makerspace=space).exists()
    assert "hidden" not in str(client.get(url).data)
    # Canonical credentials are write-only: the response reports only that they are set.
    channel = reverse("contract-channel", kwargs={"makerspace_id": space.pk, "channel": "sms"})
    # The canonical writer steps up for credentials like the retired one did.
    stale = client.patch(channel, {"credentials": OWN_SMS}, format="json")
    assert stale.status_code == 403
    reauthenticate(client, manager)
    response = client.patch(channel, {"enabled": True, "personal_enabled": True, "credentials": OWN_SMS}, format="json")
    assert response.status_code == 200 and response.data["credentials_set"] is True
    for data in (response.data, client.get(channel).data):
        assert "credentials" not in data
        assert OWN_SMS["auth_token"] not in str(data) and "fernet:" not in str(data)


def test_explicit_manager_is_admitted_to_messaging_settings(space, manager, client):
    url = reverse("messaging-settings", kwargs={"makerspace_id": space.pk})
    client.force_authenticate(manager)
    assert client.get(url).status_code == 200


def test_member_surface_is_independent_of_notifications_module(space, member, client):
    platform_sms()
    sms_channel(space)  # Consent binds to the canonical sender.
    space.enabled_modules = [key for key in space.enabled_modules if key != "notifications"]
    space.save()
    client.force_authenticate(member)
    response = client.get(reverse("member-messaging"), {"makerspace": space.pk})
    assert response.status_code == 200
    assert response.data["sms"]["phone_masked"] == "***2671"
    response = client.post(reverse("member-messaging-consent"), {"makerspace": space.pk, "channel": "sms", "action": "opted_in"}, format="json")
    assert response.status_code == 200 and response.data["sms"]["consented"]
    member.makerspace_memberships.update(status="revoked")
    assert client.get(reverse("member-messaging"), {"makerspace": space.pk}).status_code == 404


def test_control_forms_cannot_read_stored_secrets(space, manager):
    row = PlatformWhatsAppSettings()
    row.set_secret("access_token", "hidden-access")
    row.set_secret("app_secret", "hidden-secret")
    row.save()
    form = PlatformWhatsAppSettingsForm(instance=row)
    assert "access_token" not in form.fields and "app_secret" not in form.fields
    assert "hidden" not in form.as_p() and "fernet:" not in form.as_p()
    assert "auth_token" not in PlatformSmsSettingsForm().fields
    # Tenant secrets never appear in /control/: neither the retired legacy settings
    # model nor the canonical configuration's credential ciphertext.
    from apps.integrations.models_endpoints import ChannelConfiguration
    sms_channel(space, manager, credentials=OWN_SMS)
    assert MakerspaceMessagingSettings not in admin.site._registry
    assert ChannelConfiguration not in admin.site._registry


def test_bootstrap_contains_only_channel_availability(space):
    from apps.makerspaces.platform import bootstrap_payload
    assert bootstrap_payload(space)["messaging"] == {"sms": False, "whatsapp": False}


def test_all_messaging_routes_have_openapi_operations():
    from drf_spectacular.generators import SchemaGenerator
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    assert "get" in paths["/api/v1/me/messaging"]
    assert "post" in paths["/api/v1/me/messaging/consent"]
    for suffix, methods in {"messaging-settings": {"get", "patch"}, "whatsapp-templates": {"get", "post"},
                            "whatsapp-templates/{id}": {"patch", "delete"}, "whatsapp-templates/catalog": {"get"}}.items():
        path = f"/api/v1/admin/makerspace/{{makerspace_id}}/{suffix}"
        assert methods <= paths[path].keys()


def test_member_session_allowlist_is_exact_for_messaging():
    from apps.accounts.authentication import _member_surface_path_allowed
    assert _member_surface_path_allowed("/api/v1/me/messaging")
    assert _member_surface_path_allowed("/api/v1/me/messaging/consent")
    assert not _member_surface_path_allowed("/api/v1/me/messaging-admin")


def test_nonmember_and_missing_tenant_are_uniform_404(space, client):
    actor = User.objects.create_user(username="outsider-messaging")
    client.force_authenticate(actor)
    url = reverse("member-messaging")
    denied = client.get(url, {"makerspace": space.pk})
    missing = client.get(url, {"makerspace": space.pk + 999999})
    assert denied.status_code == missing.status_code == 404
    assert denied.data == missing.data
