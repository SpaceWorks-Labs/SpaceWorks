from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import close_old_connections

from apps.integrations.mail_providers.budget import BudgetDeferred, models, reserve, reset_at, settle, usage
from apps.integrations.mail_providers.budget_config import AccountBudget, account_budget, credential_fingerprint
from apps.integrations.mail_providers.config import validate_config
from apps.integrations.models_email import EmailLog


@pytest.fixture
def account():
    return AccountBudget("one-provider-account", "resend", 3, 5, "America/New_York")


def test_midnight_and_monthly_reset_follow_provider_timezone():
    now = datetime(2026, 11, 1, 3, 55, tzinfo=timezone.utc)
    assert reset_at(now, "America/New_York").astimezone(timezone.utc).isoformat() == "2026-11-01T04:00:00+00:00"
    assert reset_at(now, "America/New_York", monthly=True) == reset_at(now, "America/New_York")


def test_unconfigured_or_wrong_account_cannot_gain_a_tenant_allowance(settings):
    config = validate_config("resend", {"api_key": "one", "account_key": "shared"}, "mail@example.org")
    settings.FREE_EMAIL_ACCOUNTS = {"shared": {"provider": "resend", "daily_cap": 100,
        "monthly_cap": 3000, "reset_timezone": "UTC", "credential_fingerprints": [credential_fingerprint(config)]}}
    assert account_budget(config).daily_cap == 100
    other = validate_config("resend", {"api_key": "another", "account_key": "shared"}, "mail@example.org")
    with pytest.raises(ImproperlyConfigured, match="scope mismatch"):
        account_budget(other)
    settings.FREE_EMAIL_ACCOUNTS["shared"]["provider"] = "brevo"
    with pytest.raises(ImproperlyConfigured, match="provider mismatch"):
        account_budget(config)


@pytest.mark.django_db
def test_accepted_uncertain_and_active_reservations_share_one_cap(account):
    logs = [EmailLog.objects.create(to_email="to@example.org", subject="Test") for _ in range(4)]
    receipts = [reserve(account, log=log, attempt_key=f"attempt-{n}", recipients=1)
                for n, log in enumerate(logs[:3])]
    settle(receipts[0], "accepted", log=logs[0])
    settle(receipts[1], "uncertain", log=logs[1])
    with pytest.raises(BudgetDeferred) as result:
        reserve(account, log=logs[3], attempt_key="fourth", recipients=1)
    assert result.value.code == "email_daily_budget_reached"
    assert usage(account)["accepted"] == 1
    assert usage(account)["uncertain"] == 1
    assert usage(account)["reserved"] == 1


@pytest.mark.django_db
def test_release_is_monotonic_and_only_definite_rejection_restores_capacity(account):
    log = EmailLog.objects.create(to_email="to@example.org", subject="Test")
    receipt = reserve(account, log=log, attempt_key="accept", recipients=3)
    settle(receipt, "accepted", log=log)
    settle(receipt, "released", log=log)
    receipt.refresh_from_db()
    assert receipt.state == "accepted"
    assert reserve(account, log=log, attempt_key="accept", recipients=3).pk == receipt.pk
    with pytest.raises(BudgetDeferred):
        reserve(account, log=log, attempt_key="other", recipients=1)


@pytest.mark.django_db
def test_definitely_rejected_send_can_retry_and_midnight_does_not_reset_month(account):
    log = EmailLog.objects.create(to_email="to@example.org", subject="Test")
    first = datetime(2026, 10, 18, 18, tzinfo=timezone.utc)
    receipt = reserve(account, log=log, attempt_key="rejected", recipients=3, now=first)
    settle(receipt, "released", log=log)
    receipt = reserve(account, log=log, attempt_key="rejected", recipients=3, now=first)
    settle(receipt, "accepted", log=log, now=first)
    with pytest.raises(BudgetDeferred) as result:
        reserve(account, log=log, attempt_key="tomorrow", recipients=3,
                now=datetime(2026, 10, 19, 18, tzinfo=timezone.utc))
    assert result.value.code == "email_monthly_budget_reached"
    assert result.value.retry_at.day == 1 and result.value.retry_at.month == 11
    assert reserve(account, log=log, attempt_key="next-month", recipients=3,
                   now=datetime(2026, 11, 1, 18, tzinfo=timezone.utc))


@pytest.mark.django_db
def test_cross_reset_acceptance_and_unknown_requests_cannot_evade_next_window(account):
    log = EmailLog.objects.create(to_email="to@example.org", subject="Test")
    before = datetime(2026, 11, 1, 3, 59, tzinfo=timezone.utc)  # October in provider timezone.
    after = datetime(2026, 11, 1, 4, 1, tzinfo=timezone.utc)
    receipt = reserve(account, log=log, attempt_key="cross-midnight", recipients=3, now=before)
    settle(receipt, "accepted", log=log, now=after)
    with pytest.raises(BudgetDeferred, match="daily_budget"):
        reserve(account, log=log, attempt_key="new-day", recipients=1, now=after)


@pytest.mark.django_db
def test_uncertain_timeout_stays_charged_across_reset_until_reconciled(account):
    log = EmailLog.objects.create(to_email="to@example.org", subject="Test")
    receipt = reserve(account, log=log, attempt_key="uncertain", recipients=3,
                      now=datetime(2026, 10, 18, 18, tzinfo=timezone.utc))
    settle(receipt, "uncertain", log=log)
    # A different message: the same log is refused earlier (email_acceptance_uncertain)
    # so an unresolved send can never be duplicated; the daily window is what is tested here.
    other = EmailLog.objects.create(to_email="to@example.org", subject="Tomorrow")
    with pytest.raises(BudgetDeferred, match="daily_budget"):
        reserve(account, log=other, attempt_key="tomorrow-unknown", recipients=1,
                now=datetime(2026, 10, 19, 18, tzinfo=timezone.utc))


@pytest.mark.django_db(transaction=True)
def test_independent_connections_reserve_platform_and_tenant_mail_atomically(account):
    from apps.makerspaces.models import Makerspace
    space = Makerspace.objects.create(name="Budget", slug="budget")
    logs = [EmailLog.objects.create(to_email="to@example.org", subject="Test", makerspace=tenant)
            for tenant in (None, space)]
    ready = Barrier(2)

    def attempt(log_id):
        close_old_connections()
        try:
            log = EmailLog.objects.get(pk=log_id)
            ready.wait(timeout=10)
            try:
                reserve(account, log=log, attempt_key=f"parallel-{log_id}", recipients=2)
                return "reserved"
            except BudgetDeferred:
                return "deferred"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [log.pk for log in logs]))
    assert sorted(results) == ["deferred", "reserved"]
    assert usage(account)["reserved"] == 2
