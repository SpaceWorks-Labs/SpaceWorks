"""An in-flight writer must observe departure after waiting on the owner lock."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from apps.accounts.account_obligations import AccountDeletionPending
from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.hardware_requests.request_workflow import RequesterSnapshot, submit_request
from apps.hardware_requests.direct_loan_workflow import issue_direct_loan
from apps.machines.models import MachineServiceRequest
from apps.machines import role_scope
from apps.machines.service_workflow import accept, create_reprint, fail, start, submit
from tests.return_helpers import make_issue_evidence, make_product, make_space, make_user
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db(transaction=True)


def _writer(kind, space, owner, actor, monkeypatch):
    if kind == "request":
        product = make_product(space)
        return lambda: submit_request(
            space, [{"product": product, "quantity": 1}], requester_principal=owner,
            contact_snapshot=RequesterSnapshot(username=owner.username, name="Owner", email=owner.email, phone=""),
            audit_actor=owner,
        ), lambda: HardwareRequest.objects.filter(requester=owner).count()
    if kind == "direct_handout":
        evidence = make_issue_evidence(space, actor)
        product = make_product(space)
        monkeypatch.setattr(
            "apps.hardware_requests.direct_loan_workflow.validate_evidence_upload",
            lambda *args, **kwargs: SimpleNamespace(size=10),
        )
        monkeypatch.setattr(
            "apps.hardware_requests.direct_loan_workflow.require_active_member_presence",
            lambda *args: SimpleNamespace(membership=None),
        )
        monkeypatch.setattr(
            "apps.hardware_requests.direct_loan_workflow.require_current_term", lambda *args: None,
        )
        return lambda: issue_direct_loan(
            space, actor, borrower=owner, evidence_id=evidence.pk, remark="Handout",
            qr_payloads=[], items=[{"product_id": product.pk, "quantity": 1}],
        ), lambda: PublicToolLoan.objects.filter(requester=owner).count()
    # Exercise both the new member ownership and the documented legacy fallback.
    original = submit(
        machine(space), owner, member=owner if kind == "reprint" else None,
        requester_name="Owner", contact_email=owner.email, contact_phone="123", title="Print",
    )
    accept(original, actor)
    original = start(original, actor, role_scope.EXEMPT, machine_id=original.bucket.machine_id)
    original = fail(original, actor, reason="Fixture failure", percent_complete=0,
                    actual_minutes=0, consumptions=[])
    return lambda: create_reprint(original, actor), lambda: MachineServiceRequest.objects.filter(
        reprint_of=original,
    ).count()


@pytest.mark.parametrize("kind", ["request", "direct_handout", "reprint", "legacy_reprint"])
def test_writer_waits_for_departure_and_refuses_stale_user(kind, monkeypatch):
    space, owner, actor = make_space(f"deletion-race-{kind}"), make_user(f"owner-{kind}"), make_user(f"actor-{kind}")
    write, count = _writer(kind, space, owner, actor, monkeypatch)
    ready, worker_pid = Event(), []

    def run():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                worker_pid.append(cursor.fetchone()[0])
            ready.set()
            try:
                write()
            except AccountDeletionPending:
                return "refused"
            return "created"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = User.objects.select_for_update().get(pk=owner.pk)
            future = pool.submit(run)
            assert ready.wait(timeout=5)
            deadline, blocked = monotonic() + 5, False
            while monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_stat_clear_snapshot()")
                    cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", worker_pid)
                    row = cursor.fetchone()
                if row and row[0] == "Lock":
                    blocked = True
                    break
                if future.done():
                    break
                sleep(0.01)
            assert blocked, ("The obligation writer must wait on the locked account.", future.done() and (future.exception() or future.result()))
            locked.deletion_requested_at = timezone.now()
            locked.is_active = False
            locked.save(update_fields=["deletion_requested_at", "is_active"])
        assert future.result(timeout=10) == "refused"
    assert count() == 0
    assert owner.deletion_requested_at is None  # The caller still holds the stale object.
