"""Real DB worker races: one claim, no expiry resend, fenced provider completion."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from apps.notifications.envelope_push_leases import claim, complete
from apps.notifications.member_push import send_envelope_push
from apps.notifications.models_push import MemberPushDelivery
from apps.notifications.tasks import sweep_member_push
from tests.notifications.test_support_m1b import push_case  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


def worker(parent_id, rendered):
    from apps.integrations.models_contract import NotificationDelivery
    close_old_connections()
    try:
        return send_envelope_push(NotificationDelivery.objects.get(pk=parent_id), rendered)
    finally:
        close_old_connections()


def child(case):
    case.prepare()
    return MemberPushDelivery.objects.create(envelope_delivery=case.parent, push_device=case.device)


def test_simultaneous_claims_grant_one_token_and_increment_once(push_case):
    delivery = child(push_case)
    start = Barrier(2)

    def compete():
        close_old_connections()
        try:
            start.wait(timeout=10)
            return claim(MemberPushDelivery.objects.filter(
                pk=delivery.pk, envelope_delivery__makerspace_id=push_case.space.pk))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        tokens = [f.result(timeout=10) for f in [pool.submit(compete), pool.submit(compete)]]
    assert sum(token is not None for token in tokens) == 1
    delivery.refresh_from_db()
    assert delivery.status == "sending" and delivery.attempts == 1
    assert delivery.lease_token == next(t for t in tokens if t is not None)


def test_concurrent_workers_send_once_without_application_transaction(push_case):
    case = push_case
    delivery = child(case)
    entered, release = Event(), Event()

    def hold_http():
        assert not connection.in_atomic_block
        entered.set()
        assert release.wait(10)

    case.before_http = hold_http
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, case.parent.pk, case.rendered)
        try:
            assert entered.wait(10)
            result = pool.submit(worker, case.parent.pk, case.rendered).result(timeout=10)
            assert result.retryable and not result.accepted
        finally:
            release.set()
        assert first.result(timeout=10).accepted
    delivery.refresh_from_db()
    assert delivery.status == "sent" and delivery.attempts == 1 and len(case.calls) == 1


def test_expired_claim_is_held_without_a_second_provider_call(push_case):
    case = push_case
    delivery = child(case)
    target = MemberPushDelivery.objects.filter(pk=delivery.pk)
    token = claim(target)
    target.update(lease_until=timezone.now() - timedelta(seconds=1))
    assert claim(target) is None
    assert sweep_member_push()["enqueued"] == 0
    assert worker(case.parent.pk, case.rendered).ambiguous
    delivery.refresh_from_db()
    assert delivery.status == "held" and delivery.attempts == 1
    assert delivery.lease_token == token and case.calls == []
    # A real completion of that exact in-flight call can resolve the hold.
    assert complete(target, token, status="sent") == 1
    # The parent hold requires the canonical completion/evidence seam as well.
    assert worker(case.parent.pk, case.rendered).ambiguous and case.calls == []


def test_late_success_can_settle_its_own_expired_lease(push_case):
    case = push_case
    delivery = child(case)
    entered, release = Event(), Event()

    def hold_http():
        entered.set()
        assert release.wait(10)

    case.before_http = hold_http
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, case.parent.pk, case.rendered)
        try:
            assert entered.wait(10)
            MemberPushDelivery.objects.filter(pk=delivery.pk).update(
                lease_until=timezone.now() - timedelta(seconds=1))
            assert pool.submit(worker, case.parent.pk, case.rendered).result(timeout=10).ambiguous
        finally:
            release.set()
        assert first.result(timeout=10).accepted
    delivery.refresh_from_db()
    assert delivery.status == "sent" and delivery.attempts == 1 and len(case.calls) == 1


@pytest.mark.parametrize("status", ["sent", "failed"])
def test_account_cleanup_fences_a_stale_completion(push_case, status):
    from apps.notifications.privacy import scrub_account
    delivery = child(push_case)
    target = MemberPushDelivery.objects.filter(pk=delivery.pk)
    token = claim(target)
    scrub_account(push_case.user, push_case.space.pk)
    assert complete(target, token, status=status) == 0
    delivery.refresh_from_db()
    assert delivery.status == "canceled" and delivery.lease_token is None


@pytest.mark.parametrize("status,attempts,retryable,expected", [
    ("pending", 0, False, True), ("pending", 1, False, False),
    ("failed", 1, True, True), ("failed", 4, True, False), ("failed", 1, False, False),
    ("held", 1, False, False), ("canceled", 0, False, False),
    ("sent", 1, False, False), ("skipped", 0, False, False),
])
def test_sweep_only_enqueues_explicitly_retryable_canonical_children(push_case, status, attempts, retryable, expected):
    case = push_case
    delivery = child(case)
    MemberPushDelivery.objects.filter(pk=delivery.pk).update(status=status, attempts=attempts, retryable=retryable)
    assert sweep_member_push()["enqueued"] == int(expected)
    if expected:
        case.parent_queue.assert_called_once_with(case.envelope.pk)
    else:
        case.parent_queue.assert_not_called()
    assert case.calls == []
