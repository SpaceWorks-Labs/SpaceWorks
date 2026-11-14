"""Inactive webhook endpoints still count; credential edits never allocate another slot."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.integrations.dispatch_channels import channel_module_blocks
from apps.integrations.models_destinations import NotificationDestination
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications, pytest.mark.area_webhook]


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_webhook_disable_rotate_enable_stays_counted_and_delete_releases_capacity(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-webhook-life")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"webhook", "notifications"})
    space.resource_limit_overrides = {"webhook_endpoints": 1}
    space.save(update_fields=["enabled_modules", "resource_limit_overrides"])
    caller = callers(space, surface, settings, monkeypatch)[0]
    url = reverse("admin-notification-destinations", args=[space.pk])
    body = {"channel": "webhook", "label": "Original", "webhook_url": "https://8.8.8.8/hooks"}
    maximum = caller.post(url, body, format="json")
    assert maximum.status_code == 201
    row = NotificationDestination.objects.get(makerspace=space)
    detail = reverse("admin-notification-destination-detail", args=[space.pk, row.pk])
    edit = {"channel": "webhook", "label": "Paused", "is_active": False}
    assert caller.put(detail, edit, format="json").status_code == 200
    before = list(NotificationDestination.objects.order_by("pk").values())
    audits = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    refused = caller.post(url, {**body, "label": "Excess"}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (409, "webhook_endpoints_quota_reached")
    assert list(NotificationDestination.objects.order_by("pk").values()) == before
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == audits
    rotated = caller.post(reverse("admin-notification-destination-rotate-secret", args=[space.pk, row.pk]), {}, format="json")
    assert rotated.status_code == 200
    assert caller.put(detail, {**edit, "is_active": True}, format="json").status_code == 200
    assert NotificationDestination.objects.filter(makerspace=space).count() == 1
    # Worker gate is behavioural: disabling delivery keeps the counted credential.
    space.enabled_modules.remove("webhook")
    space.save(update_fields=["enabled_modules"])
    assert channel_module_blocks(space, "webhook") is True
    row.refresh_from_db()
    assert row.is_active is True
    assert row.webhook_url != ""
    space.enabled_modules.append("webhook")
    space.save(update_fields=["enabled_modules"])
    assert channel_module_blocks(space, "webhook") is False
    assert caller.delete(detail).status_code == 204
    restored = caller.post(url, body, format="json")
    assert restored.status_code == 201
    assert NotificationDestination.objects.filter(makerspace=space).count() == 1
