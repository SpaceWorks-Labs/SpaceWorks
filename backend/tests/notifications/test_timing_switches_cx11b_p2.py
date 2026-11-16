"""Quiet hours/digests are routeless timing policies; escalation is a bounded worker."""
from datetime import datetime, time, timedelta, timezone as utc
from uuid import uuid4

import pytest
from django.db import connection
from django.utils import timezone

from apps.integrations.digests import digest_due
from apps.integrations.models_timing import NotificationTimingPolicy
from apps.integrations.quiet_hours import quiet_until
from apps.notifications.escalation import escalate_unseen_task
from apps.notifications.models_browser_alerts import NotificationEscalation
from apps.notifications.models_inbox import MemberNotificationPreference, NotificationInboxRow
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.payments.switch_helpers_cx11b_p2 import _no_write, read_policy_cycle, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications]


@pytest.mark.parametrize("key", ["notifications.quiet_hours", "notifications.digests", "notifications"])
def test_timing_policy_ignores_retained_settings_off_and_resumes_on(key):
    space = live_space("p2-timing", MODULE_KEYS)
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    person = make_staff(space, username="p2-timing-person", access_status="active")
    policy = NotificationTimingPolicy.objects.create(makerspace=space, quiet_start=time(22), quiet_end=time(8),
        channels=["email"], digest_at=time(8))
    pref = MemberNotificationPreference.objects.create(makerspace=space, user=person, feature="bookings",
        channel="email", daily_digest=True)
    now = datetime(2026, 10, 11, 18, 30, tzinfo=utc.utc)
    due = datetime(2026, 10, 12, 2, 30, tzinfo=utc.utc)
    read = (lambda: quiet_until(space, "email", now)) if key.endswith("quiet_hours") else (
        lambda: digest_due(space, person.pk, "bookings", now))
    read_policy_cycle(space, {"policy": policy, "preference": pref}, key, read, due, None)


@pytest.mark.parametrize("key", ["notifications.escalation", "notifications"])
def test_escalation_worker_skips_off_then_escalates_retained_notice_exactly_once(key):
    space = live_space("p2-escalation", MODULE_KEYS)
    person = make_staff(space, username="p2-escalation-person", access_status="active")
    row = NotificationInboxRow.objects.create(makerspace=space, user=person, feature="hardware_requests",
        event="submitted", event_key=uuid4(), title="Private retained notice")
    NotificationInboxRow.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(minutes=40))
    original = switch(space, key)
    with connection.execute_wrapper(_no_write):
        assert escalate_unseen_task() == {"escalated": 0, "failed": 0, "skipped": 0}
    assert NotificationEscalation.objects.filter(event_key=row.event_key).count() == 0
    switch(space, key, original=original)
    assert escalate_unseen_task() == {"escalated": 1, "failed": 0, "skipped": 0}
    assert escalate_unseen_task() == {"escalated": 0, "failed": 0, "skipped": 0}
    assert NotificationEscalation.objects.get(event_key=row.event_key).rooms_posted == 0
    assert NotificationInboxRow.objects.get(pk=row.pk).title == "Private retained notice"
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(makerspace=space, action="notification.escalated").count() == 1
