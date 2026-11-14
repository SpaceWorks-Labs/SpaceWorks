"""PostgreSQL contention proofs: removing either reservation lock must fail."""
from threading import Event, Thread
from time import monotonic, sleep
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connection, connections

from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.integrations.models_document_email import DocumentEmailIntent
from apps.integrations.notification_tasks import deliver_envelope
from apps.payments.models import PaymentDocument
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_email_recovery_history import remove_marker
from tests.billing_docs.test_r2_email import assert_mail_owner, document_ledger_snapshot, issue_mail

pytestmark = pytest.mark.django_db(transaction=True)


def contend_at_envelope_lock(produce, *, legacy=False):
    """Observe contention on the existing row or the lazy-creation unique key."""
    assert connection.vendor == "postgresql"
    first_locked, second_entered, second_locked, release = Event(), Event(), Event(), Event()
    pids, errors = {}, []
    table = DocumentEmailIntent._meta.db_table

    def run(index):
        close_old_connections()
        db = connections["default"]
        try:
            with db.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
                cursor.execute("SET statement_timeout = '10s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids[index] = cursor.fetchone()[0]

            def observe(execute, sql, params, many, context):
                locked_query = "FOR UPDATE" in sql and f'FROM "{table}"' in sql
                # A pre-530 intent has no committed row yet: the second producer
                # waits on get_or_create's unique INSERT before its FOR UPDATE.
                insert_query = sql.lstrip().startswith(f'INSERT INTO "{table}"')
                if index == 2 and (insert_query if legacy else locked_query):
                    second_entered.set()
                result = execute(sql, params, many, context)
                if locked_query and index == 2:
                    second_locked.set()
                if locked_query and index == 1 and not first_locked.is_set():
                    first_locked.set()
                    assert release.wait(10), "First producer was not released"
                return result

            with db.execute_wrapper(observe):
                produce()
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()

    threads = [Thread(target=run, args=(index,), daemon=True) for index in (1, 2)]
    try:
        threads[0].start()
        assert first_locked.wait(5), "Producer did not acquire the reservation lock"
        threads[1].start()
        assert second_entered.wait(5), "Second producer did not reach the same reservation"
        assert pids[1] != pids[2]
        blockers = []
        deadline = monotonic() + 3
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_blocking_pids(%s)", [pids[2]])
                blockers = cursor.fetchone()[0]
            if pids[1] in blockers:
                break
            sleep(0.01)
        assert pids[1] in blockers, "Second producer did not wait on the first reservation"
        # The empty reservation window, not an already-visible pending attempt.
        assert EmailLog.objects.filter(event="document_issued", status="pending").count() == 0
        assert EmailLog.objects.filter(event="document_issued", status="sent").count() == 0
    finally:
        release.set()
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=12)
        assert all(not thread.is_alive() for thread in threads), "Producer exceeded its bounded timeout"
    assert errors == []
    assert second_locked.is_set(), "Second producer never acquired the shared reservation row"


@pytest.mark.parametrize("path", ["direct", "envelope"])
@pytest.mark.parametrize("pre_marker", [False, True])
def test_two_connections_reemit_document_key_with_one_reservation_and_one_send(
        document, document_mail, lane, path, pre_marker, settings,
        django_capture_on_commit_callbacks, mailoutbox):
    # Isolate this fence from the independent platform-counter row lock. The
    # source/recipient gates are real; document_mail supplies the fake transport.
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    lane.space.email_provider = "resend"
    lane.space.resource_limit_overrides = {**lane.space.resource_limit_overrides, "email": None}
    lane.space.save(update_fields=["email_provider", "resource_limit_overrides"])
    set_switch(lane.space, "email", False)
    envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    deliver_envelope(envelope.pk)
    if pre_marker:
        remove_marker(envelope)
    history = list(EmailLog.objects.filter(event="document_issued").values())
    assert len(history) == 1
    assert (history[0]["status"], history[0]["error"]) == (
        "skipped", "Email is disabled for this makerspace.")
    original = document_ledger_snapshot(document)
    set_switch(lane.space, "email", True)
    queued = lane.enqueued.count(envelope.pk)

    def produce():
        current = PaymentDocument.objects.select_related("makerspace", "payment__member").get(pk=document.pk)
        if path == "envelope":
            notify_document(current)
        else:
            # Explicit re-emission via the document-only caller path. Exercise
            # the direct reservation without emit()'s separate envelope lock.
            from apps.operations.notifications_p2 import direct_mail_unless_routed
            direct_mail_unless_routed(space=current.makerspace, source_kind="payments.document", row=current,
                revision=envelope.revision, event="document_issued", owner=current.payment.member,
                to_email=current.payment.member.email, subject="Document", text="Document issued",
                stream="payments", audience="requester", feature="", sync=True, persist_body=False,
                document_reference={"document_id": current.pk, "kind": current.kind})

    with patch("apps.integrations.dispatch._deliver", side_effect=lambda log: log) as transport:
        contend_at_envelope_lock(produce, legacy=pre_marker)
    assert transport.call_count == (1 if path == "direct" else 0)
    assert lane.enqueued.count(envelope.pk) == queued + (1 if path == "envelope" else 0)
    if path == "direct":
        pending = EmailLog.objects.get(event="document_issued", status="pending")
        assert (pending.error, pending.attempts) == ("", 0)
        assert pending.source_metadata["p2_direct"] == envelope.dedup_key
        assert EmailLog.objects.filter(event="document_issued").count() == 2
        _deliver(pending)
    else:
        assert EmailLog.objects.filter(event="document_issued").count() == 1
        deliver_envelope(envelope.pk)
    deliver_envelope(envelope.pk)
    assert len(mailoutbox) == 1 and document_mail.rendered == [document.pk]
    assert mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [
        (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert_mail_owner(document, path, envelope, skipped_direct=1)
    assert list(EmailLog.objects.filter(pk=history[0]["id"]).values()) == history
    assert document_ledger_snapshot(document) == original
