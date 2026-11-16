"""Messaging limits have worker reservation surfaces, rather than model add forms."""
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection, connections

from apps.integrations.dispatch_outbox import dispatch_email
from apps.integrations.models import DailyEmailCounter, DailyNotificationCounter, EmailLog
from apps.makerspaces.limits_reservations import reserve_notification_quota
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_notifications, pytest.mark.area_email]
CHANNELS = ["telegram", "slack", "mattermost", "discord", "webhook", "native_push", "sms", "whatsapp"]


def race(create):
    barrier = Barrier(2)

    def worker(index):
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            barrier.wait(timeout=15)
            return create(index)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, index) for index in range(2)]
        return [future.result(timeout=30) for future in futures]


@pytest.mark.parametrize("channel", CHANNELS)
def test_daily_channel_workers_racing_for_last_reservation_admit_one(channel, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-daily-channel-race")
    space.resource_limit_overrides = {channel: 1}
    space.save(update_fields=["resource_limit_overrides"])
    assert sorted(race(lambda _: reserve_notification_quota(space, channel))) == [False, True]
    assert DailyNotificationCounter.objects.get(makerspace=space, channel=channel).count == 1


def test_email_workers_racing_for_last_send_have_one_exact_refusal(settings, mailoutbox):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    space = make_space("cx7-daily-email-race")
    space.resource_limit_overrides = {"email": 1}
    space.save(update_fields=["resource_limit_overrides"])

    def create(index):
        row = dispatch_email(to_email=f"person{index}@example.com", subject="Capacity",
            text_body="Quota regression", makerspace=space, sync=True)
        return row.status, row.error

    assert sorted(race(create)) == [("failed", "Daily email limit reached for this space."), ("sent", "")]
    assert DailyEmailCounter.objects.get(makerspace=space).count == 1
    assert EmailLog.objects.filter(makerspace=space, status="sent").count() == 1
    assert EmailLog.objects.filter(makerspace=space, status="failed").count() == 1
    assert len(mailoutbox) == 1
