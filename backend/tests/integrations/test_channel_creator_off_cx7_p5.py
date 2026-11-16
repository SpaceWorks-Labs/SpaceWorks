"""529.2: channel installation controls destination admission with the typed code."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.integrations.models_destinations import NotificationDestination
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications, pytest.mark.area_webhook]


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("channel", ["webhook", "slack", "mattermost", "discord", "telegram"])
def test_creator_channel_off_is_typed_then_on_restores_same_payload(channel, surface, settings, monkeypatch):
    space = make_space("p5-channel-off")
    space.enabled_modules = sorted(set(space.enabled_modules) - {channel})
    space.save(update_fields=["enabled_modules"])
    caller = callers(space, surface, settings, monkeypatch)[0]
    body = {"channel": channel, "label": "P5 destination",
            **({"telegram_chat_id": "-100123456789"} if channel == "telegram" else
               {"webhook_url": "https://8.8.8.8/hooks"})}
    url = reverse("admin-notification-destinations", args=[space.pk])
    before = list(AuditLog.objects.filter(makerspace=space).values())
    refused = caller.post(url, body, format="json")
    assert (refused.status_code, refused.json()["code"], refused.json()["module"]) == (404, "module_disabled", channel)
    assert NotificationDestination.objects.filter(makerspace=space).count() == 0
    assert list(AuditLog.objects.filter(makerspace=space).values()) == before
    space.enabled_modules.append(channel)
    space.save(update_fields=["enabled_modules"])
    assert caller.post(url, body, format="json").status_code == 201
    assert NotificationDestination.objects.filter(makerspace=space).count() == 1
