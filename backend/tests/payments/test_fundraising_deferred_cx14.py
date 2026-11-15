"""R5: direct notification dispatch fences deferred job writes as well as workers."""

import re
from decimal import Decimal
from threading import Event, Thread
from time import monotonic, sleep
from unittest.mock import Mock

import pytest
from django.db import close_old_connections, connection, connections, transaction
from django.utils import timezone

from apps.integrations import fanout_jobs
from apps.integrations.models_contract import NotificationEnvelope
from apps.makerspaces.models import Makerspace
from apps.payments.donations import notices
from apps.payments.donations.models import Donation, DonationPledge, Sponsor, SponsorPerk
from tests.l18_local.helpers import setup, switch
from tests.modules.switch_matrix_object_helpers import _no_write
from tests.payments.test_fundraising_public_code_cx14 import code_snapshot

pytestmark = [pytest.mark.area_payments, pytest.mark.django_db(transaction=True)]


def notice_world(kind, monkeypatch, settings):
    space, manager, donor = setup("cx14-r5-notice", "finance.recurring_donations", "finance.sponsors")
    today = timezone.localdate()
    if kind == "pledge":
        row = DonationPledge.objects.create(makerspace=space, donor=donor, created_by=manager,
            amount=Decimal("25"), currency="inr", starts_on=today, next_due_on=today)
        gift = Donation.objects.create(makerspace=space, donor=donor, created_by=manager, pledge=row,
            amount=Decimal("25"), currency="inr", period_start=today, source="pledge")
        args = (row, gift)
    else:
        sponsor = Sponsor.objects.create(makerspace=space, name="Retained", created_by=manager)
        row = SponsorPerk.objects.create(makerspace=space, sponsor=sponsor, description="Retained", due_on=today)
        args = (row,)
    settings.CELERY_TASK_ALWAYS_EAGER = False
    settings.NOTIFICATION_FANOUT_VIA_CELERY = True
    monkeypatch.setattr("apps.integrations.mail_providers.budget_config.free_profile", lambda: False)
    monkeypatch.setattr(fanout_jobs, "_in_worker", lambda: False)
    assert fanout_jobs.defer_enabled() is True
    enqueue, inline = Mock(), Mock()
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", enqueue)
    monkeypatch.setattr(notices, "fanout", inline)
    monkeypatch.setattr(notices, "direct_mail_unless_routed", inline)
    return space, getattr(notices, f"notify_{kind}_due"), args, enqueue, inline


def retained(space):
    return (code_snapshot(space), list(SponsorPerk.objects.order_by("pk").values()),
            list(NotificationEnvelope.objects.order_by("pk").values()))


def forbidden_writes(attempts):
    def check(execute, sql, params, many, context):
        if re.match(r"\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b", sql, re.I):
            attempts.append(sql)
        return _no_write(execute, sql, params, many, context)
    return check


def dispatch_after_disable(space, dispatch, args, key, attempts):
    """A separate dispatcher must block on the real disabler's makerspace lock."""
    assert connection.vendor == "postgresql"
    started, finished = Event(), Event()
    results, errors, pids = [], [], []

    def send():
        close_old_connections()
        db = connections["default"]
        try:
            with db.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids.append(cursor.fetchone()[0])
            started.set()
            with db.execute_wrapper(forbidden_writes(attempts)):
                results.append(dispatch(*args))
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()
            finished.set()

    thread = Thread(target=send, daemon=True)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                disabler_pid = cursor.fetchone()[0]
            locked = Makerspace.objects.select_for_update().get(pk=space.pk)
            locked.enabled_features = sorted(set(locked.enabled_features) - {key})
            locked.save(update_fields=["enabled_features"])
            thread.start()
            assert started.wait(5), errors
            blockers, deadline = [], monotonic() + 3
            while monotonic() < deadline and not finished.is_set():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_blocking_pids(%s)", [pids[0]])
                    blockers = cursor.fetchone()[0]
                if disabler_pid in blockers:
                    break
                sleep(0.01)
            assert disabler_pid in blockers, (errors, results)
            assert not finished.is_set()
        thread.join(timeout=10)
    finally:
        if thread.ident is not None:
            thread.join(timeout=10)
    assert not thread.is_alive()
    assert errors == []
    assert len(results) == 1
    return results[0]


@pytest.mark.parametrize("kind,key", [
    ("pledge", "finance.donations"), ("pledge", "finance.recurring_donations"),
    ("perk", "finance.donations"), ("perk", "finance.sponsors"),
])
@pytest.mark.parametrize("contended", [False, True], ids=["already-off", "disable-race"])
def test_direct_deferred_entries_refuse_before_sql_and_restore_one_job(
        kind, key, contended, monkeypatch, settings, caplog):
    space, dispatch, args, enqueue, inline = notice_world(kind, monkeypatch, settings)
    before, attempts = retained(space), []
    if contended:
        result = dispatch_after_disable(space, dispatch, args, key, attempts)
    else:
        switch(space, key, on=False)
        with connection.execute_wrapper(forbidden_writes(attempts)):
            result = dispatch(*args)
    assert (result.scheduled, result.failed_counts) == (False, {"outbox": 1})
    failures = [record.failure_type for record in caplog.records if record.msg == "domain_notification_failed"]
    assert failures == ["SurfaceOff"]
    assert attempts == []  # Detect attempted writes even when safe_notification swallowed the assertion.
    assert retained(space) == before
    enqueue.assert_not_called()
    inline.assert_not_called()
    space.refresh_from_db()
    switch(space, key)
    result = dispatch(*args)
    assert (result.scheduled, result.failed_counts) == (True, {})
    assert code_snapshot(space) == before[0]
    assert list(SponsorPerk.objects.order_by("pk").values()) == before[1]
    envelopes = NotificationEnvelope.objects.exclude(pk__in=[row["id"] for row in before[2]])
    assert envelopes.count() == 1
    job = envelopes.get()
    expected = f"apps.payments.donations.notices.notify_{kind}_due"
    assert (job.makerspace_id, job.source_kind, job.event) == (space.pk, "legacy.lifecycle", f"notify_{kind}_due")
    assert job.context["fanout"]["fn"] == expected
    assert job.context["fanout"]["state"] == "queued"
    assert [arg["pk"] for arg in job.context["fanout"]["args"]] == [row.pk for row in args]
    enqueue.assert_called_once_with(job.pk)
    inline.assert_not_called()


@pytest.mark.parametrize("kind,key", [
    ("pledge", "finance.donations"), ("pledge", "finance.recurring_donations"),
    ("perk", "finance.donations"), ("perk", "finance.sponsors"),
])
def test_registered_worker_retains_fresh_child_check(kind, key, monkeypatch, settings):
    from apps.makerspaces.guards import SurfaceOff

    space, _dispatch, args, enqueue, inline = notice_world(kind, monkeypatch, settings)
    switch(space, key, on=False)
    before, attempts = retained(space), []
    worker = fanout_jobs.REGISTRY[f"apps.payments.donations.notices.notify_{kind}_due"]
    with connection.execute_wrapper(forbidden_writes(attempts)), pytest.raises(SurfaceOff) as refused:
        worker(*args)
    assert (refused.value.status_code, str(refused.value.detail["code"])) == (404, "feature_disabled")
    assert refused.value.key == key
    assert attempts == []
    assert retained(space) == before
    enqueue.assert_not_called()
    inline.assert_not_called()


def test_settled_receipt_still_defers_with_fundraising_off(monkeypatch, settings):
    space, _dispatch, args, enqueue, inline = notice_world("pledge", monkeypatch, settings)
    donation = args[1]
    donation.status, donation.paid_at = "paid", timezone.now()
    donation.save(update_fields=["status", "paid_at"])
    switch(space, "finance.donations", on=False)
    before = code_snapshot(space)
    result = notices.notify_receipt(donation)
    assert (result.scheduled, result.failed_counts) == (True, {})
    job = NotificationEnvelope.objects.get(source_kind="legacy.lifecycle")
    assert job.context["fanout"]["fn"] == "apps.payments.donations.notices.notify_receipt"
    assert code_snapshot(space) == before
    enqueue.assert_called_once_with(job.pk)
    inline.assert_not_called()
