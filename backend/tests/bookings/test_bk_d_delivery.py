"""Shared worker retry, quiet-hours, digest and source-gate seams with booking adapters."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations import delivery_sources
from apps.integrations.delivery_content import content
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.operations.reminder_sweeper import run_reminder_sweep
from tests.bookings.bk_d_helpers import fixture, queued, smtp

pytestmark = pytest.mark.django_db(transaction=True)


def test_campaign_retry_rechecks_cancellation_without_second_outbox(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign, delivery, log = queued(resource, sender)
    send = smtp(monkeypatch, side_effect=RuntimeError("SMTP unavailable"))
    _deliver(log)
    assert log.status == "failed"
    from apps.bookings.services_broadcasts import change
    change(campaign, sender, "cancel")
    send.reset_mock(); send.side_effect = None
    _deliver(log)
    assert not send.called and log.status == "skipped"
    assert campaign.deliveries.count() == 1
    assert EmailLog.objects.filter(source_kind="booking_broadcast").count() == 1


@pytest.mark.parametrize("address_gate", ["none", "old_suppressed", "current_suppressed", "unverified"])
def test_campaign_quiet_release_uses_live_email_and_never_digest(monkeypatch, address_gate):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    now = timezone.now(); clock = [now]; due = now+timedelta(hours=1)
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    monkeypatch.setattr("apps.integrations.quiet_hours.quiet_until", lambda space, channel, at: due if at < due else None)
    monkeypatch.setattr("apps.integrations.timing_dispatch.quiet_until", lambda space, channel, at: due if at < due else None)
    monkeypatch.setattr("apps.integrations.digests.digest_due", lambda *args: pytest.fail("campaign entered digest assignment"))
    campaign, delivery, log = queued(resource, sender)
    assert log.error.startswith("deferred:email:") and not delivery_sources.digestible(log)
    from apps.accounts.models import User
    User.objects.filter(pk=user.pk).update(email="changed@example.test",
                                          email_verified_at=None if address_gate == "unverified" else now)
    if address_gate in {"old_suppressed", "current_suppressed"}:
        from apps.integrations.email_preferences import address_hash
        from apps.integrations.models_suppression import EmailSuppression
        address = user.email if address_gate == "old_suppressed" else "changed@example.test"
        EmailSuppression.objects.create(makerspace=tenant, address_hash=address_hash(tenant.pk, address), reason="bounce")
    send = smtp(monkeypatch)
    clock[0] = due+timedelta(seconds=1)
    result = run_reminder_sweep(now=clock[0], source_keys=["notifications.deferred"])
    assert result["failed"] == 0
    log.refresh_from_db()
    delivery.refresh_from_db()
    campaign.refresh_from_db()
    if address_gate in {"none", "old_suppressed"}:
        assert send.call_count == 1 and log.status == delivery.status == campaign.status == "sent"
        assert send.call_args.args[0].to == ["changed@example.test"]
    else:
        assert not send.called and log.status == delivery.status == "skipped"
    run_reminder_sweep(now=clock[0], source_keys=["notifications.deferred"])
    assert send.call_count == (1 if address_gate in {"none", "old_suppressed"} else 0)
    assert not EmailLog.objects.filter(source_kind="notification_digest").exists()


def test_manual_digest_marker_cannot_aggregate_booking_campaign(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign, delivery, log = queued(resource, sender)
    from apps.operations.reminder_services import schedule_reminders
    now = timezone.now()
    log.error = f"deferred:digest:{now.isoformat()}"; log.save(update_fields=["error"])
    schedule_reminders(makerspace=tenant, source="notifications.deferred", subject=f"digest:{user.pk}:{now.isoformat()}", kind="digest", due_at=now)
    send = smtp(monkeypatch)
    run_reminder_sweep(now=now, source_keys=["notifications.deferred"])
    assert send.call_count == 1
    assert not EmailLog.objects.filter(source_kind="notification_digest").exists()


def test_source_gate_freeze_blocks_both_batch_and_delivery(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign, delivery, log = queued(resource, sender)
    from tests.tenant_migration.source_gate_helpers import close_gate
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    from apps.integrations.broadcasts_worker import broadcast_batch, resume_broadcasts
    close_gate(tenant, manager)
    send = smtp(monkeypatch)
    with pytest.raises(SourceMigrationGateClosed):
        _deliver(log)
    with pytest.raises(SourceMigrationGateClosed):
        broadcast_batch("booking_broadcast", campaign.pk)
    resume_broadcasts()
    assert not send.called
    log.refresh_from_db(); assert log.status == "pending"


def test_tombstoned_adapter_and_unknown_source_never_deliver(monkeypatch):
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign, delivery, log = queued(resource, sender)
    monkeypatch.delitem(delivery_sources.SOURCES, "booking_broadcast")
    send = smtp(monkeypatch)
    _deliver(log)
    assert log.status == "skipped" and not send.called


def test_booking_lost_between_selection_and_render_skips_safely(monkeypatch):
    from dataclasses import replace
    from apps.integrations.broadcasts_registry import ADAPTERS
    from apps.bookings.services_transitions import cancel_booking
    tenant, manager, sender, resource, grant, user, booking = fixture(monkeypatch)
    campaign, delivery, log = queued(resource, sender)
    adapter = ADAPTERS["booking_broadcast"]
    def render_after_cancellation(campaign, recipient):
        cancel_booking(booking, actor=user, member_cancel=True)
        return adapter.render(campaign, recipient)
    monkeypatch.setitem(ADAPTERS, "booking_broadcast", replace(adapter, render=render_after_cancellation))
    send = smtp(monkeypatch)
    _deliver(log)
    assert log.status == "skipped" and not send.called
