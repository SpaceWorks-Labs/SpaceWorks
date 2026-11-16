"""Retention cutoffs are exclusive; unread/in-flight and other-tenant rows survive."""
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations.models import EmailLog, NotificationDeliveryLog
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.retention import run_notification_retention, sweep_tenant_retention
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("model", [EmailLog, NotificationDeliveryLog])
def test_only_terminal_logs_older_than_their_own_cutoff_are_deleted(model):
    space, other = make_space("cx4-retention"), make_space("cx4-retention-other")
    now = timezone.now()
    edge90, edge365 = now - timedelta(days=90), now - timedelta(days=365)
    microsecond = timedelta(microseconds=1)

    def row(tenant, status, at):
        data = {"makerspace": tenant, "status": status, "event": "cx4", "text_body": ""}
        if model is EmailLog:
            data.update(to_email="member@example.test", subject="Test")
        else:
            data.update(channel="webhook", feature="payments")
        log = model.objects.create(**data)
        model.objects.filter(pk=log.pk).update(sent_at=at if status == "sent" else None, updated_at=at)
        return log.pk

    deleted = [row(space, "sent", edge90 - microsecond), row(space, "skipped", edge90 - microsecond),
               row(space, "failed", edge365 - microsecond)]
    kept = [row(space, "sent", edge90), row(space, "skipped", edge90), row(space, "failed", edge365),
            row(space, "pending", edge365 - microsecond), row(other, "sent", edge365 - microsecond)]
    assert sweep_tenant_retention(space, now=now, limit=10) == 3
    assert set(model.objects.values_list("pk", flat=True)) == set(kept)
    assert model.objects.filter(pk__in=deleted).count() == 0
    assert sweep_tenant_retention(space, now=now, limit=10) == 0


def test_unread_inbox_and_cutoff_read_are_retained_and_limit_is_respected():
    space = make_space("cx4-inbox-retention")
    member = make_member("cx4-inbox-member", space, membership_role="custom")
    now = timezone.now()
    cutoff = now - timedelta(days=90)
    rows = [NotificationInboxRow.objects.create(makerspace=space, user=member, event_key=uuid.uuid4(),
        feature="payments", event="charge_raised", title="Charge", read_at=at)
        for at in (None, cutoff, cutoff - timedelta(seconds=1), cutoff - timedelta(seconds=2))]
    assert sweep_tenant_retention(space, now=now, limit=1) == 1
    assert set(NotificationInboxRow.objects.values_list("pk", flat=True)) == {rows[0].pk, rows[1].pk, rows[3].pk}
    assert sweep_tenant_retention(space, now=now, limit=1) == 1
    assert set(NotificationInboxRow.objects.values_list("pk", flat=True)) == {rows[0].pk, rows[1].pk}


@pytest.mark.parametrize("limit", [0, -1, True, None, "1"])
def test_invalid_batch_limit_fails_before_any_deletion(limit):
    with pytest.raises(ValueError, match="^Notification retention batch size must be a positive integer\\.$"):
        run_notification_retention(now=timezone.now(), limit=limit)
