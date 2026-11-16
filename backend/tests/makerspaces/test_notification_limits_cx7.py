"""Explicit daily caps protect shared capacity on both hosting modes (decision 281)."""
import pytest
from django.utils import timezone

from apps.integrations.models import DailyNotificationCounter
from apps.makerspaces.limits_reservations import reserve_notification_quota
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("domain_suffix", ["", ".space-works.tech"])
@pytest.mark.parametrize("channel", ["telegram", "slack", "mattermost", "discord", "webhook", "native_push", "sms", "whatsapp"])
def test_daily_limit_accepts_max_refuses_next_and_keeps_tenants_separate(settings, domain_suffix, channel):
    settings.PLATFORM_DOMAIN_SUFFIX = domain_suffix
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-notification-cap")
    other = make_space("cx7-other-notification")
    space.resource_limit_overrides = {channel: 1}
    space.save(update_fields=["resource_limit_overrides"])
    assert reserve_notification_quota(space, channel) is True
    assert reserve_notification_quota(space, channel) is False
    assert DailyNotificationCounter.objects.get(makerspace=space, channel=channel).count == 1
    assert reserve_notification_quota(other, channel) is True
    assert DailyNotificationCounter.objects.filter(makerspace=other).count() == 0
    assert DailyNotificationCounter.objects.get(makerspace=space, channel=channel).day == timezone.now().date()


@pytest.mark.parametrize("cap, expected", [(0, False), (None, True), (-1, True)])
def test_zero_and_explicit_unlimited_are_respected_on_self_host(settings, cap, expected):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-notification-zero")
    space.resource_limit_overrides = {"discord": cap}
    space.save(update_fields=["resource_limit_overrides"])
    assert reserve_notification_quota(space, "discord") is expected
    assert not DailyNotificationCounter.objects.filter(makerspace=space, count__gt=0).exists()


@pytest.mark.parametrize("suffix", ["", ".space-works.tech"])
def test_email_daily_last_slot_and_next_delivery_have_exact_outcomes(suffix, settings, mailoutbox):
    from apps.integrations.dispatch_outbox import dispatch_email
    from apps.integrations.models import DailyEmailCounter, EmailLog
    settings.PLATFORM_DOMAIN_SUFFIX = suffix
    settings.MANAGED_PLANS_ENABLED = False
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    space = make_space("cx7-email-boundary")
    space.resource_limit_overrides = {"email": 1}
    space.save(update_fields=["resource_limit_overrides"])
    logs = [dispatch_email(to_email="recipient@example.com", subject=f"Quota {n}",
        text_body="Quota test", makerspace=space, sync=True) for n in range(2)]
    assert [row.status for row in logs] == [EmailLog.Status.SENT, EmailLog.Status.FAILED]
    assert logs[1].error == "Daily email limit reached for this space."
    assert len(mailoutbox) == 1
    assert DailyEmailCounter.objects.get(makerspace=space).count == 1
