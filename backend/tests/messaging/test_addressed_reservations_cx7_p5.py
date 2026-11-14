"""Canonical addressed reservations, including the retained overqueued refusal."""
import pytest
from django.db import connection

from apps.integrations.models import DailyNotificationCounter
from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_quotas import reserve
from tests.messaging.canonical_helpers import (
    envelope, platform_sms, platform_whatsapp, sms_channel, whatsapp_channel,
)
from tests.makerspaces.test_daily_delivery_creator_races_cx7 import race

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications, pytest.mark.area_sms, pytest.mark.area_whatsapp]


def deliveries(space, member, channel):
    if channel == "sms":
        platform_sms()
        config = sms_channel(space)
    else:
        platform_whatsapp()
        config = whatsapp_channel(space)
    rows = []
    for index in range(2):
        intent = envelope(space, member, key=f"p5-addressed-{index}")
        rows.append(NotificationDelivery.objects.create(envelope=intent, makerspace=space,
            channel=channel, target_key=f"recipient:{member.pk}", provider=config.provider,
            provider_source="platform", sender_key=config.sender_key))
    return rows


@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_canonical_daily_max_next_and_retry_reuse_the_same_reservation(space, member, channel, settings):
    settings.MANAGED_PLANS_ENABLED = False
    rows = deliveries(space, member, channel)
    space.resource_limit_overrides = {channel: 1}
    space.save(update_fields=["resource_limit_overrides"])
    assert reserve(rows[0]) is True
    assert reserve(rows[1]) is False
    assert reserve(rows[0]) is True
    rows[0].refresh_from_db()
    rows[1].refresh_from_db()
    assert rows[0].quota_reserved_at is not None
    assert rows[1].quota_reserved_at is None
    assert DailyNotificationCounter.objects.get(makerspace=space, channel=channel).count == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_canonical_daily_creators_contend_for_one_slot(space, member, channel, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    rows = deliveries(space, member, channel)
    space.resource_limit_overrides = {channel: 1}
    space.save(update_fields=["resource_limit_overrides"])
    assert sorted(race(lambda index: reserve(rows[index]))) == [False, True]
    assert NotificationDelivery.objects.filter(quota_reserved_at__isnull=False).count() == 1
    assert DailyNotificationCounter.objects.get(makerspace=space, channel=channel).count == 1


@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_platform_monthly_max_then_next_refuses_without_spending_daily_capacity(space, member, channel, settings):
    settings.MANAGED_PLANS_ENABLED = False
    first, second = deliveries(space, member, channel)
    # The Nth row is inclusive when it is the only queued intent.
    second.delete()
    space.resource_limit_overrides = {channel: 2, f"platform_{channel}_monthly": 1}
    space.save(update_fields=["resource_limit_overrides"])
    assert reserve(first) is True
    second = NotificationDelivery.objects.create(envelope=envelope(space, member, key="p5-next"),
        makerspace=space, channel=channel, target_key=f"recipient:{member.pk}",
        provider=first.provider, provider_source="platform", sender_key=first.sender_key)
    assert reserve(second) is False
    assert DailyNotificationCounter.objects.get(makerspace=space, channel=channel).count == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_overqueued_platform_worker_refuses_both_instead_of_over_admitting(space, member, channel, settings):
    """P4b source finding: this is a capacity-utilization GAP, not a bypass fix."""
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    rows = deliveries(space, member, channel)
    space.resource_limit_overrides = {channel: 2, f"platform_{channel}_monthly": 1}
    space.save(update_fields=["resource_limit_overrides"])
    assert race(lambda index: reserve(rows[index])) == [False, False]
    assert NotificationDelivery.objects.filter(quota_reserved_at__isnull=False).count() == 0
    assert DailyNotificationCounter.objects.filter(makerspace=space, channel=channel).count() == 0
