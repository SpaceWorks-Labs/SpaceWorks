from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_delivery import apply_callback, ensure_deliveries, send
from apps.integrations.notification_providers import CallbackEvent, ProviderResult
from apps.notifications.models_preferences import NotificationPreference

pytestmark = pytest.mark.django_db


def delivery(c):
    NotificationPreference.objects.create(makerspace=c.space, user=c.user,
        category="hardware_requests", channels=["telegram"], email_fallback=True)
    envelope = c.envelope()
    ensure_deliveries(envelope)
    return envelope.deliveries.get(channel="telegram")


def test_send_and_callback_duplicates_never_regress(contract):
    c = contract
    row = delivery(c)
    send(row.pk)
    row.refresh_from_db()
    assert row.state == "accepted"
    send(row.pk)
    assert len(c.fake.calls) == 1
    for state in ["delivered", "sent", "read", "delivered", "failed", "read"]:
        apply_callback(c.config, CallbackEvent(provider_id=row.provider_id, state=state))
    row.refresh_from_db()
    assert row.state == "read"


def test_retry_budget_is_bounded(contract):
    c = contract
    row = delivery(c)
    c.fake.results = [ProviderResult(False, retryable=True, error_code="unavailable")] * 10
    for _ in range(8):
        NotificationDelivery.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        send(row.pk)
    row.refresh_from_db()
    assert row.attempt_count == 4 and row.state == "failed"
    assert len(c.fake.calls) == 4
    assert row.envelope.deliveries.filter(channel="email").count() == 1


def test_ambiguous_timeout_retries_once_then_falls_back(contract):
    c = contract
    row = delivery(c)
    c.fake.results = [ProviderResult(False, retryable=True, error_code="timeout", ambiguous=True)] * 3
    for _ in range(3):
        NotificationDelivery.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        send(row.pk)
    row.refresh_from_db()
    assert row.attempt_count == 2 and row.state == "failed"
    assert row.envelope.deliveries.filter(channel="email").count() == 1


def test_withdrawn_source_and_consent_block_queued_send(contract):
    c = contract
    row = delivery(c)
    c.state["valid"] = False
    send(row.pk)
    row.refresh_from_db()
    assert row.state == "skipped" and not c.fake.calls


def test_callback_cannot_cross_provider_generation(contract):
    c = contract
    row = delivery(c)
    send(row.pk)
    row.refresh_from_db()
    c.config.generation += 1
    c.config.save()
    assert not apply_callback(c.config, CallbackEvent(provider_id=row.provider_id, state="read"))
    row.refresh_from_db()
    assert row.state == "accepted"


def test_no_provider_text_is_persisted(contract):
    c = contract
    row = delivery(c)
    c.fake.results = [ProviderResult(False, error_code="token=secret", sanitized_error="phone: +1234567")]
    send(row.pk)
    row.refresh_from_db()
    assert row.last_error == "provider_error"


def test_revoked_preference_during_retry_blocks_transport(contract):
    c = contract
    row = delivery(c)
    c.fake.results = [ProviderResult(False, retryable=True, error_code="unavailable")]
    send(row.pk)
    c.endpoint.revoked_at = timezone.now()
    c.endpoint.save(update_fields=["revoked_at"])
    NotificationDelivery.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    send(row.pk)
    row.refresh_from_db()
    assert row.state == "skipped" and len(c.fake.calls) == 1


def test_provider_budget_counts_attempt_day_and_recipient(contract, monkeypatch):
    from apps.integrations.notification_quotas import reserve
    c = contract
    row = delivery(c)
    monkeypatch.setattr("apps.makerspaces.limits.reserve_notification_quota", lambda *args: True)
    c.config.quotas = {"daily_limit": 10, "recipient_daily_limit": 1}
    c.config.save()
    assert reserve(row) is True
    assert reserve(row) is False
    c.config.refresh_from_db()
    c.config.usage["day"] = (timezone.now() - timedelta(days=1)).date().isoformat()
    c.config.save(update_fields=["usage"])
    assert reserve(row) is True


def test_crashed_last_attempt_exhausts_instead_of_staying_retrying(contract):
    from apps.integrations.notification_delivery import MAX_ATTEMPTS, claim
    c = contract
    row = delivery(c)
    row.attempt_count = MAX_ATTEMPTS
    row.claim_until = timezone.now() - timedelta(seconds=1)
    row.save()
    assert claim(row.pk) is None
    row.refresh_from_db()
    assert row.state == "failed" and row.claim_until is None
