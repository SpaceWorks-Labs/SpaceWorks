"""Legacy blank features retain their normalized family when a digest is rebuilt."""

from datetime import datetime, timedelta, timezone as utc

import pytest
from django.utils import timezone

from apps.integrations.dispatch import dispatch_email
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog, NotificationPreference
from apps.integrations.models_timing import NotificationTimingPolicy
from apps.operations.reminder_sweeper import run_reminder_sweep
from tests.events.lane_d_helpers import smtp
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("stream,family", [
    ("events", "events"), ("bookings", "bookings"), ("hardware", "hardware_requests"),
])
def test_blank_feature_digest_rebuilds_and_sends_only_its_family(monkeypatch, stream, family):
    space = make_space("legacy-digest")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"email", "notifications", "events", "bookings"})
    space.enabled_features = sorted(set(space.enabled_features) | {"notifications.digests"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    user = make_member("digest-owner", space)
    other = make_member("digest-other", space)
    NotificationPreference.objects.create(makerspace=space, feature=family, channel="email", enabled=True)
    # Tenant defaults also apply to legacy rows without an explicit feature.
    NotificationTimingPolicy.objects.create(makerspace=space, daily_digest_default=True, channels=[])
    now = datetime(2026, 10, 11, 5, tzinfo=utc.utc)
    monkeypatch.setattr(timezone, "now", lambda: now)
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda pk: None)
    send = smtp(monkeypatch)
    original = dispatch_email(
        makerspace=space, recipient_id=user.pk, to_email=user.email, feature="", stream=stream,
        event="created", subject="Legacy update", text_body="Keep this legacy input", sync=True,
    )
    assert original.error.startswith("deferred:digest:")
    send.assert_not_called()
    now += timedelta(days=1)
    run_reminder_sweep(now=now, source_keys={"notifications.deferred"})
    summary = EmailLog.objects.get(makerspace=space, event="daily_digest")
    assert summary.feature == family and summary.source_metadata["entries"] == [original.pk]

    # Retained IDs alone must never admit another family, recipient or tenant.
    foreign_space = make_space("foreign-digest")
    excluded = [EmailLog.objects.create(
        makerspace=tenant, recipient=recipient, to_email=user.email,
        feature=feature, stream=stream, subject="Excluded", text_body="Do not include",
        status="skipped", error="included_in_daily_digest",
    ) for tenant, recipient, feature in [
        (space, user, "members"), (space, other, family), (foreign_space, user, family),
    ]]
    summary.source_metadata["entries"].extend(mail.pk for mail in excluded)
    summary.save(update_fields=["source_metadata"])
    _deliver(summary)
    summary.refresh_from_db()
    assert summary.status == "sent" and summary.attempts == 1
    send.assert_called_once()
    from apps.integrations.delivery_content import content
    assert content(summary).text_body == "Legacy update\nKeep this legacy input"
