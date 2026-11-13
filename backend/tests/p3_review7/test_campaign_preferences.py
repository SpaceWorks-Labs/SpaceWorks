"""Campaign category choices govern both pipelines, including retries and fallback."""
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.integrations.broadcasts_worker import broadcast_batch
from apps.integrations.models import EmailLog, NotificationPreference as TenantPreference
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_delivery import ensure_deliveries, send
from apps.integrations.notification_providers import ProviderResult
from apps.notifications.models_preferences import NotificationPreference
from tests.p3_review5.test_campaign_recovery import campaign_for

pytestmark = pytest.mark.django_db
KINDS = ["event_broadcast", "booking_broadcast", "member_broadcast"]
CATEGORIES = {"event_broadcast": "events", "booking_broadcast": "bookings", "member_broadcast": "members"}


def setup_campaign(world, kind):
    world.owner.email_verified_at = timezone.now()
    world.owner.save(update_fields=["email_verified_at"])
    if kind == "member_broadcast":
        world.space.enabled_modules = sorted(set(world.space.enabled_modules) | {"email", "membership", "notifications"})
        world.space.save(update_fields=["enabled_modules"])
        campaign, change, source = None, None, "membership.broadcast"
    else:
        campaign, change, source = campaign_for(world, kind)
    category = CATEGORIES[kind]
    TenantPreference.objects.update_or_create(makerspace=world.space, feature=category,
        channel="email", defaults={"enabled": True})
    # The round-5 booking fixture starts with personal choices; each case controls its own.
    NotificationPreference.objects.filter(makerspace=world.space, user=world.owner, category=category).delete()
    return campaign, change, source


def run_campaign(world, kind, campaign, change, source):
    if kind == "member_broadcast":
        from apps.notifications.broadcasts import send_broadcast
        campaign, _ = send_broadcast(world.space, actor=world.staff, title="News", body="Open today")
    else:
        change(campaign, world.staff, "queue")
        broadcast_batch(kind, campaign.pk)
    envelope = NotificationEnvelope.objects.filter(source_kind=source, source_id=str(campaign.pk),
                                                   recipient=world.owner).first()
    return campaign, envelope


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("channels", [["telegram"], ["in_app"], []])
def test_non_email_choice_without_fallback_never_queues_campaign_email(world, kind, channels):
    args = setup_campaign(world, kind)
    NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category=CATEGORIES[kind], channels=channels, email_fallback=False)
    campaign, envelope = run_campaign(world, kind, *args)
    assert envelope is not None
    ensure_deliveries(envelope)
    ensure_deliveries(envelope, fallback=True)  # exhaustion must not override recipient consent
    assert not envelope.deliveries.filter(channel="email").exists()
    assert not EmailLog.objects.filter(source_kind=kind, recipient=world.owner).exists()
    if kind != "member_broadcast":
        assert not campaign.deliveries.filter(recipient=world.owner).exists()


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("direct_email", [False, True])
@pytest.mark.parametrize("tenant_fallback", [False, True])
def test_selected_email_or_permitted_fallback_uses_one_pipeline(
        world, monkeypatch, kind, direct_email, tenant_fallback):
    args = setup_campaign(world, kind)
    world.config("email", provider="builtin", email_fallback=tenant_fallback)
    NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category=CATEGORIES[kind], channels=["email"] if direct_email else ["telegram"],
        email_fallback=not direct_email)
    campaign, envelope = run_campaign(world, kind, *args)
    # No Telegram endpoint: fallback is necessary. Tenant permission gates fallback,
    # while an explicit email selection does not need fallback permission.
    ensure_deliveries(envelope)
    ensure_deliveries(envelope, fallback=True)
    emails = envelope.deliveries.filter(channel="email")
    assert emails.count() == int(direct_email or tenant_fallback)
    transport = Mock(return_value=ProviderResult(True, "mail-1"))
    monkeypatch.setattr("apps.integrations.notification_builtin.send_builtin", transport)
    for row in emails:
        send(row.pk)
        send(row.pk)
    if kind != "member_broadcast":
        broadcast_batch(kind, campaign.pk)
        assert not campaign.deliveries.filter(recipient=world.owner).exists()
    assert transport.call_count == int(direct_email or tenant_fallback)
    assert not EmailLog.objects.filter(source_kind=kind, recipient=world.owner).exists()


@pytest.mark.parametrize("kind", KINDS)
def test_personal_email_retry_rechecks_saved_selection(world, monkeypatch, kind):
    args = setup_campaign(world, kind)
    choice = NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category=CATEGORIES[kind], channels=["email"], email_fallback=True)
    _, envelope = run_campaign(world, kind, *args)
    ensure_deliveries(envelope)
    delivery = envelope.deliveries.get(channel="email")
    transport = Mock(return_value=ProviderResult(False, retryable=True, error_code="provider_error"))
    monkeypatch.setattr("apps.integrations.notification_builtin.send_builtin", transport)
    send(delivery.pk)
    delivery.refresh_from_db()
    assert delivery.state == "retrying"
    choice.channels, choice.email_fallback = ["telegram"], False
    choice.save()
    delivery.next_attempt_at = timezone.now()
    delivery.save(update_fields=["next_attempt_at"])
    send(delivery.pk)
    delivery.refresh_from_db()
    assert delivery.state == "skipped" and transport.call_count == 1


@pytest.mark.parametrize("kind", ["event_broadcast", "booking_broadcast"])
@pytest.mark.parametrize("retry", [False, True])
def test_queued_legacy_email_honors_new_selection_before_send_or_retry(world, monkeypatch, kind, retry):
    from apps.integrations.dispatch_delivery import _deliver
    from tests.bookings.bk_d_helpers import smtp
    args = setup_campaign(world, kind)
    campaign, _ = run_campaign(world, kind, *args)
    delivery = campaign.deliveries.get(recipient=world.owner)
    log = delivery.outbox
    transport = smtp(monkeypatch)
    if retry:
        transport.side_effect = OSError("offline")
        _deliver(log)
        assert log.status == "failed" and transport.call_count == 1
        transport.reset_mock()
        transport.side_effect = None
    NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category=CATEGORIES[kind], channels=["telegram"], email_fallback=False)
    _deliver(log)
    assert log.status == "skipped" and not transport.called
    delivery.refresh_from_db()
    assert delivery.status == "skipped"


@pytest.mark.parametrize("kind", ["event_broadcast", "booking_broadcast"])
@pytest.mark.parametrize("direct_email", [False, True])
@pytest.mark.parametrize("tenant_fallback", [False, True])
def test_new_selection_after_legacy_dispatch_preserves_permitted_email_once(
        world, monkeypatch, kind, direct_email, tenant_fallback):
    from apps.integrations.dispatch_delivery import _deliver
    from tests.bookings.bk_d_helpers import smtp
    args = setup_campaign(world, kind)
    campaign, _ = run_campaign(world, kind, *args)
    log = campaign.deliveries.get(recipient=world.owner).outbox
    transport = smtp(monkeypatch)
    transport.side_effect = OSError("offline")
    _deliver(log)
    assert log.status == "failed"
    transport.reset_mock()
    transport.side_effect = None
    world.config("email", provider="builtin", email_fallback=tenant_fallback)
    NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category=CATEGORIES[kind], channels=["email"] if direct_email else ["telegram"],
        email_fallback=not direct_email)
    _deliver(log)
    envelope = NotificationEnvelope.objects.get(source_kind=args[2], source_id=str(campaign.pk), recipient=world.owner)
    ensure_deliveries(envelope)
    for delivery in envelope.deliveries.filter(channel="email"):
        send(delivery.pk)
        send(delivery.pk)
    expected = int(direct_email or tenant_fallback)
    assert transport.call_count == expected
    assert EmailLog.objects.filter(recipient=world.owner, event="broadcast", status="sent").count() == expected


def test_removing_saved_event_choice_does_not_switch_to_parallel_legacy_email(world):
    from apps.events.broadcasts import eligible
    args = setup_campaign(world, "event_broadcast")
    choice = NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category="events", channels=["email"], email_fallback=False)
    campaign, envelope = run_campaign(world, "event_broadcast", *args)
    choice.delete()
    assert not eligible(campaign, world.owner)
    ensure_deliveries(envelope)
    assert envelope.deliveries.filter(channel="email").count() == 1
    assert not campaign.deliveries.filter(recipient=world.owner).exists()


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("gate", ["none", "unverified", "unsubscribe", "module"])
def test_no_saved_choice_preserves_existing_email_gates(world, kind, gate):
    args = setup_campaign(world, kind)
    campaign, envelope = run_campaign(world, kind, *args)
    if gate == "unverified":
        world.owner.email_verified_at = None
        world.owner.save(update_fields=["email_verified_at"])
    elif gate == "unsubscribe":
        from apps.notifications.models import MemberNotificationPreference
        MemberNotificationPreference.objects.create(makerspace=world.space, user=world.owner,
            feature=CATEGORIES[kind], channel="email", enabled=False)
    elif gate == "module":
        world.space.enabled_modules.remove("email")
        world.space.save(update_fields=["enabled_modules"])
    if kind == "member_broadcast":
        ensure_deliveries(envelope)
        allowed = envelope.deliveries.filter(channel="email").exists()
    else:
        from apps.integrations.broadcasts_delivery import prepare
        allowed = prepare(campaign.deliveries.get(recipient=world.owner).outbox)
        if kind == "event_broadcast":
            assert list(envelope.deliveries.values_list("channel", "state")) == [("email", "skipped")]
    assert allowed is (gate == "none")
