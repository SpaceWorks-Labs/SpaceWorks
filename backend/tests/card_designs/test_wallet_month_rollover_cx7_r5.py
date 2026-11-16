"""The first successful wallet issuance, rather than queue age, owns a slot."""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.card_designs import storage
from apps.card_designs.models import WalletPass
from apps.card_designs.wallet import apple, content, google, service
from apps.managed_hosting import platform_limits
from tests.card_designs.test_wallet_worker_limits_cx7_p4b import setup, snapshot
from tests.limits_0120.creator_races_cx7 import race_creators

pytestmark = [pytest.mark.django_db, pytest.mark.area_membership]
BEFORE = datetime(2026, 11, 30, 23, 59, 59, tzinfo=UTC)
AFTER = datetime(2026, 12, 1, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch, settings):
    settings.MANAGED_PLANS_ENABLED = False
    value = SimpleNamespace(now=BEFORE)
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return value.now.astimezone(tz) if tz is not None else value.now.replace(tzinfo=None)
    monkeypatch.setattr(timezone, "now", lambda: value.now)
    monkeypatch.setattr(audit, "datetime", FrozenDateTime)
    monkeypatch.setattr(platform_limits, "datetime", FrozenDateTime)
    return value


def builders(monkeypatch):
    build = Mock(return_value=b"signed-pass")
    save = Mock(wraps=google.save_link)
    put = Mock()
    contents = Mock(wraps=content.pass_content)
    monkeypatch.setattr(apple, "build_pkpass", build)
    monkeypatch.setattr(google, "save_link", save)
    monkeypatch.setattr(storage, "put_bytes", put)
    monkeypatch.setattr(service, "pass_content", contents)
    return build, save, put, contents


def set_cap(space, cap):
    space.resource_limit_overrides = {"platform_wallet_monthly": cap}
    space.save(update_fields=["resource_limit_overrides"])


def assert_refused(job):
    with pytest.raises(APIException) as failure:
        service.issue_from_job(job)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (400, "platform_wallet_limit_reached")


@pytest.mark.parametrize("platform", ["apple", "google"])
def test_prior_month_unsigned_job_at_zero_refuses_before_building_with_unchanged_rows(clock, platform, monkeypatch):
    space, jobs = setup(monkeypatch, platform=platform)
    assert list(WalletPass.objects.filter(makerspace=space).values_list("created_at", flat=True)) == [BEFORE, BEFORE]
    clock.now = AFTER
    set_cap(space, 0)
    calls = builders(monkeypatch)
    # Re-requesting the queued row does not turn it into an already issued pass.
    row = WalletPass.objects.get(pk=jobs[0].params["pass_id"])
    same, job = service.request_pass(jobs[0].requested_by, "member_card", row.member_card, platform)
    assert (same.pk, job.pk) == (row.pk, jobs[0].pk)
    before = snapshot()
    assert_refused(job)
    assert snapshot() == before
    for call in calls:
        call.assert_not_called()
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 0
    assert AuditLog.objects.filter(makerspace=space, action="wallet_pass.issued").count() == 0


@pytest.mark.parametrize("platform", ["apple", "google", "mixed"])
def test_two_prior_month_unsigned_jobs_share_one_current_month_slot(clock, platform, monkeypatch):
    space, jobs = setup(monkeypatch, platform=platform)
    calls = builders(monkeypatch)
    clock.now = AFTER
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 0
    assert service.issue_from_job(jobs[0]) is True
    issued = AuditLog.objects.get(makerspace=space, action="wallet_pass.issued")
    assert (issued.created_at, issued.meta) == (AFTER, {
        "pass_id": jobs[0].params["pass_id"], "platform": jobs[0].params["platform"], "source": "platform"})
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 1
    before = snapshot()
    for call in calls:
        call.reset_mock()
    assert_refused(jobs[1])
    assert snapshot() == before
    for call in calls:
        call.assert_not_called()
    assert AuditLog.objects.filter(makerspace=space, action="wallet_pass.issued").count() == 1
    assert WalletPass.objects.filter(makerspace=space, content_digest="").count() == 1
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("platform", ["apple", "google", "mixed"])
def test_delayed_workers_racing_after_rollover_have_exactly_one_slot(clock, platform, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, jobs = setup(monkeypatch, platform=platform)
    clock.now = AFTER
    assert race_creators(lambda index: service.issue_from_job(jobs[index])) == [
        (201, "created"), (400, "platform_wallet_limit_reached")]
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 1
    assert AuditLog.objects.filter(makerspace=space, action="wallet_pass.issued", created_at=AFTER).count() == 1
    assert WalletPass.objects.filter(makerspace=space, content_digest="").count() == 1


@pytest.mark.parametrize("platform", ["apple", "google"])
def test_previously_issued_prior_month_pass_reissues_at_zero_without_new_slot(clock, platform, monkeypatch):
    space, jobs = setup(monkeypatch, platform=platform)
    assert service.issue_from_job(jobs[0]) is True
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 1
    original = AuditLog.objects.get(makerspace=space, action="wallet_pass.issued")
    assert original.created_at == BEFORE
    clock.now = AFTER
    set_cap(space, 0)
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 0
    assert service.issue_from_job(jobs[0]) is True
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 0
    assert list(AuditLog.objects.filter(makerspace=space, action="wallet_pass.issued").order_by("pk").values_list(
        "created_at", flat=True)) == [BEFORE, AFTER]
    assert WalletPass.objects.filter(makerspace=space).count() == 2
    assert_refused(jobs[1])


def test_prior_month_unsigned_own_credentials_still_issue_at_zero(clock, monkeypatch):
    space, jobs = setup(monkeypatch, own=True)
    clock.now = AFTER
    assert [service.issue_from_job(job) for job in jobs] == [True, True]
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 0
    assert list(AuditLog.objects.filter(makerspace=space, action="wallet_pass.issued").values_list(
        "created_at", "meta__source")) == [(AFTER, "space"), (AFTER, "space")]


@pytest.mark.parametrize("field,key", [("enabled_modules", "membership"),
                                       ("enabled_features", "membership.wallet_passes")])
def test_delayed_job_switches_keep_rows_then_restore_current_month_admission(clock, field, key, monkeypatch):
    space, jobs = setup(monkeypatch)
    clock.now = AFTER
    saved = getattr(space, field)
    setattr(space, field, [value for value in saved if value != key])
    space.save(update_fields=[field])
    before = snapshot()
    assert service.issue_from_job(jobs[0]) is False
    assert snapshot() == before
    setattr(space, field, saved)
    space.save(update_fields=[field])
    assert service.issue_from_job(jobs[0]) is True
    assert platform_limits.platform_used(space, "platform_wallet_monthly") == 1
    assert_refused(jobs[1])
