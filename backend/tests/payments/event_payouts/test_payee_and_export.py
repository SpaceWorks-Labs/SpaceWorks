"""Finance-only reveal, correction revisions, terminal purge and masked batches."""
from datetime import timedelta
import json
from uuid import uuid4
import pytest
from django.db import connection
from django.utils import timezone
from apps.audit.models import AuditLog
from apps.payments.event_payouts import exports, payee_workflow, payout_workflow
from apps.payments.event_payouts.errors import PayoutError
from apps.payments.event_payouts.payee_models import EventPayeeRevision
from apps.payments.event_payouts.retention import purge_payees
from apps.payments.event_payouts.worker_boundary import locked_obligation
from .conftest import request_for
from .test_ledger import ready_payee, record_data

pytestmark = pytest.mark.django_db(transaction=True)


def test_single_reveal_is_audited_no_values_in_metadata_or_ordinary_response(finance_bundle):
    b = finance_bundle
    payee = ready_payee(b)
    b.obligation.refresh_from_db()
    value = {"operation_id": uuid4(), "expected_version": b.obligation.version,
        "expected_payee_version": payee.version, "purpose": "verify_routing", "reason_code": "routing_verification"}
    for _ in range(2):
        result = payee_workflow.reveal(request=request_for(b.actor, value), obligation_id=b.obligation.pk, data=value)
        assert result["details"]["holder_name"] == "Private owner"
    audits = AuditLog.objects.filter(action="finance.event_payout.payee_revealed")
    assert audits.count() == 2 and "Private owner" not in json.dumps(list(audits.values("meta")))
    assert "Private owner" not in json.dumps(payee_workflow.projection(payee))
    with connection.cursor() as cursor:
        cursor.execute("SELECT details FROM payments_eventpayeerevision WHERE id=%s", [payee.pk])
        raw = cursor.fetchone()[0]
    assert raw.startswith("pii:gcm:v1:") and "Private owner" not in raw


def test_correction_requires_new_owner_revision_before_verification(finance_bundle, settings):
    b = finance_bundle
    payee = ready_payee(b)
    b.obligation.refresh_from_db()
    command = {"operation_id": uuid4(), "expected_version": b.obligation.version, "payee_revision_id": payee.pk,
        "expected_payee_version": payee.version, "reason_code": "owner_correction", "note": "Please confirm routing."}
    payee_workflow.review(request=request_for(b.actor, command), obligation_id=b.obligation.pk, data=command, verified=False)
    b.obligation.refresh_from_db(); payee.refresh_from_db()
    verify = {**command, "operation_id": uuid4(), "expected_version": b.obligation.version, "expected_payee_version": payee.version}
    with pytest.raises(PayoutError):
        payee_workflow.review(request=request_for(b.actor, verify), obligation_id=b.obligation.pk, data=verify, verified=True)
    settings.EVENT_PAYOUT_TENANT_POLICIES = {str(b.space.pk): {"templates": [["IN", "cash", "cash", 1]]}}
    put = {"operation_id": uuid4(), "expected_version": b.obligation.version, "expected_payee_version": payee.version,
        "country": "IN", "method": "cash", "template_key": "cash", "template_version": 1,
        "details": {"holder_name": "Corrected owner"}, "disclosure_version": 1}
    result = payee_workflow.put(request=request_for(b.owner, put), obligation_id=b.obligation.pk, data=put)
    assert result["payee_revision_id"] != str(payee.pk)
    payee.refresh_from_db()
    assert payee.state == "superseded" and payee.details == json.dumps({"holder_name": "Private owner"})


def test_fully_paid_payload_purges_and_amendment_can_reopen_without_resurrection(finance_bundle):
    b = finance_bundle
    payee = ready_payee(b)
    data = record_data(b.obligation, payee, 150000)
    first = payout_workflow.record(request=request_for(b.actor, data), obligation_id=b.obligation.pk, data=data)
    b.obligation.refresh_from_db()
    assert purge_payees(b.obligation.pk, now=b.obligation.terminal_financial_at + timedelta(days=31)) == 1
    payee.refresh_from_db()
    assert payee.state == "purged" and payee.details == ""
    amendment = {**data, "operation_id": uuid4(), "expected_version": b.obligation.version,
        "amount_minor": 140000, "reason_code": "recording_error", "is_void": False}
    payout_workflow.amend(request=request_for(b.actor, amendment), obligation_id=b.obligation.pk,
        entry_id=first["entry_id"], data=amendment)
    payee.refresh_from_db(); b.obligation.refresh_from_db()
    assert payee.state == "purged" and payee.details == "" and b.obligation.state == "open"


def test_csv_preview_matches_download_and_batch_stales_after_payment(finance_bundle):
    import csv
    from io import StringIO
    b = finance_bundle
    payee = ready_payee(b)
    data = {"operation_id": uuid4(), "expected_version": 0, "obligation_ids": [b.obligation.pk]}
    request = request_for(b.actor, data)
    result = exports.create(request=request, makerspace_id=b.space.pk, data=data)
    payload = exports.download(request=request, makerspace_id=b.space.pk, batch_id=result["id"])
    assert list(csv.DictReader(StringIO(payload))) == [{key: str(value) for key, value in result["preview"][0].items()}]
    assert "Private owner" not in payload and "holder_name" not in payload
    record = record_data(b.obligation, payee, 1)
    payout_workflow.record(request=request_for(b.actor, record), obligation_id=b.obligation.pk, data=record)
    with pytest.raises(PayoutError) as caught:
        exports.download(request=request, makerspace_id=b.space.pk, batch_id=result["id"])
    assert str(caught.value.detail["code"]) == "batch_stale"
