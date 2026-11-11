from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.integrations.mail_providers.budget import reserve, settle, BudgetDeferred
from apps.integrations.mail_providers.budget_config import AccountBudget
from apps.integrations.models import EmailLog


@pytest.mark.django_db
def test_new_attempt_number_cannot_evade_unknown_acceptance():
    account = AccountBudget("shared", "resend", 100, 1000, "UTC")
    log = EmailLog.objects.create(to_email="mail@example.org", subject="Test")
    receipt = reserve(account, log=log, attempt_key=f"{log.pk}:0:0:content", recipients=1)
    settle(receipt, "uncertain", log=log)
    with pytest.raises(BudgetDeferred, match="email_acceptance_uncertain"):
        reserve(account, log=log, attempt_key=f"{log.pk}:0:1:content", recipients=1)


@pytest.mark.django_db
def test_accepted_crash_recovery_survives_attempt_increment():
    account = AccountBudget("shared", "resend", 100, None, "UTC")
    log = EmailLog.objects.create(to_email="mail@example.org", subject="Test")
    receipt = reserve(account, log=log, attempt_key=f"{log.pk}:0:0:content", recipients=1)
    settle(receipt, "accepted", log=log, provider_message_id="provider-id")
    recovered = reserve(account, log=log, attempt_key=f"{log.pk}:0:1:content", recipients=1)
    assert recovered.pk == receipt.pk and recovered.provider_message_id == "provider-id"


@pytest.mark.django_db
def test_no_age_or_operator_override_can_release_uncertainty(monkeypatch):
    from apps.integrations.mail_providers.reconciliation import reconcile
    account = AccountBudget("shared", "resend", 100, None, "UTC")
    log = EmailLog.objects.create(to_email="mail@example.org", subject="Test")
    receipt = reserve(account, log=log, attempt_key=f"{log.pk}:0:0:content", recipients=1)
    settle(receipt, "uncertain", log=log)
    actor = SimpleNamespace(is_active=True, is_superuser=True, account_kind="platform")
    monkeypatch.setattr("apps.integrations.mail_providers.reconciliation.require_operator", lambda actor: actor)
    with pytest.raises(ValueError, match="requires_provider_evidence"):
        reconcile(reservation_id=receipt.pk, actor=actor, evidence={"version": 1,
            "reservation_id": receipt.pk, "outcome": "confirmed_not_accepted", "source": "expired_timeout",
            "reference": "case-123", "observed_at": timezone.now().isoformat(), "attempt_key": receipt.attempt_key})
    receipt.refresh_from_db()
    assert receipt.state == "uncertain"
