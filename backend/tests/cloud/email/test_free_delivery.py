import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from apps.integrations.mail_providers.budget import BudgetDeferred
from apps.integrations.mail_providers.delivery import definite_nonacceptance, send
from apps.integrations.mail_providers.outbox import claim_due, defer_delivery, delivery_deadline, enqueue_inline_allowed
from apps.integrations.models_email import EmailLog


def mail():
    return EmailMultiAlternatives("Subject", "Redacted secret", "from@example.org", ["to@example.org"])


@pytest.mark.parametrize("profile", ["full", ""])
def test_full_delivery_ignores_all_free_caps_and_deadlines(settings, profile):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = profile
    settings.FREE_EMAIL_DAILY_CAP = 0
    log = SimpleNamespace(pk=1, attempts=0, retry_generation=0)
    with patch("apps.integrations.mail_providers.delivery.reserve") as reserve:
        with delivery_deadline(time.monotonic() - 100):
            msg = mail()
            with patch.object(msg, "send", return_value=1):
                assert send(log, msg) == 1
    reserve.assert_not_called()
    assert enqueue_inline_allowed()


def test_content_idempotency_survives_attempt_count_and_mime_boundary_changes(settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    log = SimpleNamespace(pk=1, attempts=0, retry_generation=0)
    keys = []
    for attempt in range(2):
        log.attempts = attempt
        msg = mail()
        msg.attach_alternative("<p>Secret</p>", "text/html")
        msg.attach("receipt.pdf", b"%PDF", "application/pdf")
        with patch.object(msg, "send", return_value=1):
            send(log, msg)
        keys.append(msg.spaceworks_idempotency_key)
    assert keys[0] == keys[1]
    assert "Redacted" not in keys[0]


def test_timeout_is_uncertain_but_auth_rejection_is_definite():
    from apps.integrations.mail_providers.sendgrid import ProviderRejected
    assert not definite_nonacceptance(requests.Timeout("secret"))
    assert not definite_nonacceptance(ProviderRejected(503))
    assert definite_nonacceptance(ProviderRejected(401))


@pytest.mark.django_db
def test_budget_deferral_keeps_persistent_mail_pending_and_otp_terminal(settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    tomorrow = timezone.now() + timedelta(days=1)
    log = EmailLog.objects.create(to_email="to@example.org", subject="Notice", text_body="Persisted")
    defer_delivery(log, BudgetDeferred("email_daily_budget_reached", tomorrow))
    log.refresh_from_db()
    assert log.status == EmailLog.Status.PENDING
    assert not claim_due(log) and not enqueue_inline_allowed()
    assert claim_due(log, now=tomorrow)
    otp = EmailLog.objects.create(to_email="to@example.org", subject="OTP")
    otp._timing_ineligible = True
    defer_delivery(otp, BudgetDeferred("email_daily_budget_reached", tomorrow))
    otp.refresh_from_db()
    assert otp.status == EmailLog.Status.FAILED and not otp.email_retryable
    assert not otp.text_body
    assert enqueue_inline_allowed(sync=True, persist_body=False)
    assert not enqueue_inline_allowed(sync=True, persist_body=True)


def test_no_new_send_starts_after_tick_deadline(settings):
    from apps.integrations.mail_providers.delivery import delivery_timeout
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    with delivery_deadline(time.monotonic()):
        with pytest.raises(BudgetDeferred, match="tick_budget"):
            delivery_timeout()


@pytest.mark.django_db
def test_free_send_never_holds_an_outer_row_transaction_during_provider_io(settings):
    from django.core.exceptions import ImproperlyConfigured
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    msg = mail()
    with patch.object(msg, "send") as provider:
        with pytest.raises(ImproperlyConfigured, match="after transaction commit"):
            send(SimpleNamespace(pk=1, attempts=0, retry_generation=0), msg)
    provider.assert_not_called()


@pytest.mark.parametrize("outcome", ["accepted", "uncertain", "released"])
def test_provider_outcome_updates_reservation_conservatively(settings, outcome):
    from apps.integrations.mail_providers.config import validate_config
    from apps.integrations.mail_providers.sendgrid import ProviderRejected
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    msg = mail()
    msg.connection = SimpleNamespace(spaceworks_mail_config=validate_config(
        "resend", {"api_key": "secret"}, "mail@example.org"))
    log = SimpleNamespace(pk=1, attempts=0, retry_generation=0)
    receipt = SimpleNamespace(state="reserved")
    error = requests.Timeout() if outcome == "uncertain" else ProviderRejected(401)
    with patch("apps.integrations.mail_providers.delivery.account_budget"), \
         patch("apps.integrations.mail_providers.delivery.reserve", return_value=receipt), \
         patch("apps.integrations.mail_providers.delivery.settle") as settle:
        with patch.object(msg, "send", return_value=1, side_effect=None if outcome == "accepted" else error):
            if outcome == "accepted":
                assert send(log, msg) == 1
            else:
                with pytest.raises(Exception):
                    send(log, msg)
    assert settle.call_args.args[1] == outcome


def test_accepted_receipt_recovers_provider_id_without_a_second_send(settings):
    from apps.integrations.mail_providers.config import validate_config
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    msg = mail()
    msg.connection = SimpleNamespace(spaceworks_mail_config=validate_config(
        "resend", {"api_key": "secret"}, "mail@example.org"))
    receipt = SimpleNamespace(state="accepted", provider_message_id="accepted-provider-id")
    with patch("apps.integrations.mail_providers.delivery.account_budget"), \
         patch("apps.integrations.mail_providers.delivery.reserve", return_value=receipt), \
         patch.object(msg, "send") as provider:
        assert send(SimpleNamespace(pk=1, attempts=0, retry_generation=0), msg) == 1
    provider.assert_not_called()
    assert msg.spaceworks_provider_message_id == "accepted-provider-id"


@pytest.mark.django_db
def test_bounded_drain_recovers_pending_failed_and_does_not_queue_old_otp(settings, monkeypatch):
    from apps.integrations.mail_providers.outbox import drain
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    old_otp = EmailLog.objects.create(to_email="to@example.org", subject="OTP")
    pending = EmailLog.objects.create(to_email="to@example.org", subject="Pending", text_body="Stored")
    failed = EmailLog.objects.create(to_email="to@example.org", subject="Failed", text_body="Stored", status="failed")
    future = EmailLog.objects.create(to_email="to@example.org", subject="Tomorrow", text_body="Stored",
                                    email_retry_at=timezone.now() + timedelta(days=1))
    delivered = []

    def deliver(log):
        delivered.append(log.pk)
        log.status = "sent"
        log.save(update_fields=["status"])

    monkeypatch.setattr("apps.integrations.dispatch_delivery._deliver", deliver)
    result = drain(monotonic_deadline=time.monotonic() + 20, limit=1)
    assert result["remaining"] and not delivered
    result = drain(monotonic_deadline=time.monotonic() + 20, limit=2, cursor=result["cursor"])
    assert delivered == [pending.pk, failed.pk]
    old_otp.refresh_from_db()
    future.refresh_from_db()
    assert old_otp.email_retryable is False
    assert future.status == "pending"
