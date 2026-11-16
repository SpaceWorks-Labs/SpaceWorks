"""A staff alert's per-device workers reserve the platform allowance before sending."""
import pytest
from django.db import connection

from apps.integrations.models import NotificationDeliveryLog, NotificationRecipient, PlatformPushSettings, PushDevice
from apps.integrations.models_endpoints import ChannelConfiguration
from apps.integrations.models_tracking import PushDeliveryAttempt
from apps.integrations.push import deliver_native_push
from tests.makerspaces.test_daily_delivery_creator_races_cx7 import race
from tests.return_helpers import make_space
from tests.test_native_push import device_client, push_member

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications, pytest.mark.area_mobile]


def setup(settings, monkeypatch, devices=2):
    settings.PUSH_TOKEN_HMAC_KEY = "h" * 64
    space = make_space("cx7-p4b-push")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"bookings"})
    space.enabled_features = sorted(set(space.enabled_features) | {"mobile.push"})
    space.resource_limit_overrides = {"platform_push_monthly": 1}
    space.save(update_fields=["enabled_modules", "enabled_features", "resource_limit_overrides"])
    member = push_member("cx7-p4b-push-person", space)
    NotificationRecipient.objects.create(makerspace=space, feature="bookings", event="created", kind="user", user=member)
    for index in range(devices):
        client, _ = device_client(member, space, platform="android")
        response = client.post("/api/v1/integrations/push/devices", {
            "token": str(index) * 64, "provider": "fcm", "environment": "development"}, format="json")
        assert response.status_code == 201
    platform = PlatformPushSettings.load()
    platform.set_fcm_service_account('{"configured": true}')
    platform.save()
    sent = []
    monkeypatch.setattr("apps.integrations.push.send_fcm", lambda *args: sent.append(args[1]))
    return space, sent


def log(space):
    return NotificationDeliveryLog.objects.create(makerspace=space, feature="bookings", event="created",
        channel="native_push", text_body="Booking created", status="pending")


def test_one_alert_with_two_devices_sends_only_the_last_platform_delivery(settings, monkeypatch):
    space, sent = setup(settings, monkeypatch)
    row = log(space)
    assert deliver_native_push(row) is True
    assert sorted(PushDeliveryAttempt.objects.filter(delivery_log=row).values_list("status", "last_error")) == [
        ("sent", ""), ("skipped", "platform_credential_limit_reached")]
    assert len(sent) == 1
    before = list(PushDeliveryAttempt.objects.filter(delivery_log=row).order_by("pk").values())
    assert deliver_native_push(row) is True
    assert list(PushDeliveryAttempt.objects.filter(delivery_log=row).order_by("pk").values()) == before
    assert len(sent) == 1
    assert PushDevice.objects.filter(makerspace=space, active=True).count() == 2


@pytest.mark.django_db(transaction=True)
def test_parallel_staff_push_workers_share_one_remaining_monthly_delivery(settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, sent = setup(settings, monkeypatch, devices=1)
    rows = [log(space), log(space)]
    assert race(lambda index: deliver_native_push(rows[index])) == [True, True]
    assert sorted(PushDeliveryAttempt.objects.filter(delivery_log__in=rows).values_list("status", "last_error")) == [
        ("sent", ""), ("skipped", "platform_credential_limit_reached")]
    assert len(sent) == 1


@pytest.mark.parametrize("switch", ["mobile.push", "use_platform_sender"])
def test_push_switch_off_does_not_reserve_capacity_and_on_restores_the_worker(switch, settings, monkeypatch):
    space, sent = setup(settings, monkeypatch, devices=1)
    if switch == "mobile.push":
        saved = space.enabled_features
        space.enabled_features = [key for key in saved if key != switch]
        space.save(update_fields=["enabled_features"])
    else:
        config = ChannelConfiguration.objects.create(makerspace=space, channel="native_push", provider="builtin",
                                                      use_platform_sender=False)
    row = log(space)
    assert deliver_native_push(row) is False
    assert PushDeliveryAttempt.objects.filter(delivery_log=row).count() == 0
    assert sent == []
    if switch == "mobile.push":
        space.enabled_features = saved
        space.save(update_fields=["enabled_features"])
    else:
        config.use_platform_sender = True
        config.save(update_fields=["use_platform_sender"])
    row.makerspace = space
    assert deliver_native_push(row) is True
    assert list(PushDeliveryAttempt.objects.filter(delivery_log=row).values_list("status", "last_error")) == [("sent", "")]
    assert len(sent) == 1
