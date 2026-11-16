"""Upstream room fan-out spends once per destination; provider I/O is replaced."""
import pytest
from django.db import connection

from apps.integrations.dispatch_channels import dispatch_channel
from apps.integrations.dispatch_outbox import dispatch_email
from apps.integrations.models import DailyEmailCounter, DailyNotificationCounter, EmailLog
from tests.makerspaces.test_daily_delivery_creator_races_cx7 import race
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.test_notification_destinations import capture_sends, telegram_destination, webhook_destination

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications, pytest.mark.area_email]
CHANNELS = ["telegram", "slack", "mattermost", "discord", "webhook"]


def setup(channel, monkeypatch):
    space = live_space("cx7-p4b-fanout", MODULE_KEYS)
    space.resource_limit_overrides = {channel: 1}
    space.save(update_fields=["resource_limit_overrides"])
    if channel == "telegram":
        space.set_telegram_bot_token("test-token")
        space.save()
        telegram_destination(space, "One")
        telegram_destination(space, "Two", "-100200301")
    else:
        rooms = [webhook_destination(space, channel, "One"),
                 webhook_destination(space, channel, "Two", "https://hooks.example/two")]
        if channel == "webhook":
            for room in rooms:
                room.set_signing_secret("cx7-p4b-test-signing-secret")
                room.save(update_fields=["signing_secret"])
    sent = capture_sends(monkeypatch)
    monkeypatch.setattr("apps.integrations.webhooks.send_signed_webhook",
                        lambda envelope: sent.append({"channel": "webhook"}) or True)
    return space, sent


def fanout(space, channel):
    return dispatch_channel(makerspace=space, channel=channel, feature="maintenance", event="logged",
                            text_body="Machine needs attention", sync=True)


@pytest.mark.parametrize("channel", CHANNELS)
def test_upstream_fanout_last_destination_sends_next_records_exact_failure(channel, monkeypatch):
    space, sent = setup(channel, monkeypatch)
    rows = fanout(space, channel)
    assert sorted((row.status, row.error) for row in rows) == [
        ("failed", f"Daily {channel} notification limit reached for this space."), ("sent", "")]
    assert len(sent) == 1
    assert DailyNotificationCounter.objects.get(makerspace=space, channel=channel).count == 1
    again = fanout(space, channel)
    assert [(row.status, row.error) for row in again] == [
        ("failed", f"Daily {channel} notification limit reached for this space.")] * 2
    assert len(sent) == 1
    assert DailyNotificationCounter.objects.get(makerspace=space, channel=channel).count == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("channel", CHANNELS)
def test_parallel_upstream_fanouts_share_one_last_destination_slot(channel, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, sent = setup(channel, monkeypatch)
    results = race(lambda _: [(row.status, row.error) for row in fanout(space, channel)])
    assert sorted(item for batch in results for item in batch) == [
        ("failed", f"Daily {channel} notification limit reached for this space.")] * 3 + [("sent", "")]
    assert len(sent) == 1
    assert DailyNotificationCounter.objects.get(makerspace=space, channel=channel).count == 1


@pytest.mark.parametrize("key", ["email", "platform_email_monthly"])
def test_email_creator_last_send_then_exact_refusal(key, settings, mailoutbox):
    settings.MANAGED_PLANS_ENABLED = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    space = live_space("cx7-p4b-platform-email", MODULE_KEYS)
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    send = lambda index: dispatch_email(to_email=f"member{index}@example.test", subject="Quota", text_body="Proof",
                                         makerspace=space, sync=True)
    assert (send(0).status, len(mailoutbox)) == ("sent", 1)
    refused = send(1)
    expected = ("failed", "Daily email limit reached for this space.") if key == "email" else (
        "skipped", "This space has used the emails sent with the platform mail account this month allowed by the platform (1).")
    assert (refused.status, refused.error) == expected
    assert len(mailoutbox) == 1
    assert EmailLog.objects.filter(makerspace=space, status="sent").count() == 1


@pytest.mark.django_db(transaction=True)
def test_platform_email_workers_racing_for_last_monthly_send_admit_one(settings, mailoutbox):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    space = live_space("cx7-p4b-platform-email-race", MODULE_KEYS)
    space.resource_limit_overrides = {"platform_email_monthly": 1}
    space.save(update_fields=["resource_limit_overrides"])
    results = race(lambda index: dispatch_email(to_email=f"member{index}@example.test", subject="Quota",
        text_body="Proof", makerspace=space, sync=True))
    assert sorted((row.status, row.error) for row in results) == [("sent", ""), ("skipped",
        "This space has used the emails sent with the platform mail account this month allowed by the platform (1).")]
    assert len(mailoutbox) == 1
    assert EmailLog.objects.filter(makerspace=space, provider_source="platform", status="sent").count() == 1
    assert DailyEmailCounter.objects.filter(makerspace=space).count() == 0


@pytest.mark.parametrize("channel", CHANNELS)
def test_channel_module_off_spends_no_fanout_quota_and_on_restores_destinations(channel, monkeypatch):
    space, sent = setup(channel, monkeypatch)
    saved = space.enabled_modules
    space.enabled_modules = [key for key in saved if key != channel]
    space.save(update_fields=["enabled_modules"])
    rows = fanout(space, channel)
    assert [(row.status, row.error) for row in rows] == [("skipped", "notification_channel_module_disabled")]
    assert DailyNotificationCounter.objects.filter(makerspace=space, channel=channel).count() == 0
    assert sent == []
    space.enabled_modules = saved
    space.save(update_fields=["enabled_modules"])
    restored = fanout(space, channel)
    assert sorted((row.status, row.error) for row in restored) == [
        ("failed", f"Daily {channel} notification limit reached for this space."), ("sent", "")]
    assert len(sent) == 1
