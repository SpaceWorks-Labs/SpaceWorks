"""Owner-only listing of a payout's own routing documents: metadata, never storage keys."""
import json
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.payments.event_payouts.attachment_models import FinanceAttachment
from apps.payments.event_payouts.payee_models import EventPayeeRevision
from tests.accounts.test_reauthentication import request as session_request

pytestmark = pytest.mark.django_db(transaction=True)


def payee(bundle, state="current"):
    return EventPayeeRevision.objects.create(obligation=bundle.obligation, owner=bundle.owner, country="IN",
        template_key="bank", template_version=1, method="bank", state=state,
        details=json.dumps({"holder_name": "Private owner"}), submitted_at=timezone.now(), disclosure_version=1)


def document(bundle, revision, *, state="ready", name="bank letter.pdf"):
    key = uuid4().hex
    return FinanceAttachment.objects.create(makerspace=bundle.space, event=bundle.event, event_id_snapshot=bundle.event.pk,
        event_title_snapshot=bundle.event.title, owner_member=bundle.owner, obligation=bundle.obligation,
        purpose="reimbursement_payee_document", binding_kind="payee", binding_uuid=revision.pk,
        question_id="routing_document", state=state, expected_bytes=2048, declared_mime="application/pdf",
        original_filename=name, staging_key=f"finance/staging/{key}", object_key=f"finance/final/{key}",
        scanner_policy="none", retention_policy_revision=1, retention_days_snapshot=2555)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user, token=session_request(user, surface="member").auth)
    return client


def test_owner_lists_only_live_documents_of_the_current_payee_revision(finance_bundle):
    b = finance_bundle
    old = payee(b, state="superseded")
    current = payee(b)
    kept = document(b, current)
    document(b, current, state="deleted", name="gone.pdf")
    document(b, current, state="expired", name="expired.pdf")
    document(b, old, name="old revision.pdf")
    path = reverse("member-event-payee-file-create", kwargs={"obligation_id": b.obligation.pk})
    response = client_for(b.owner).get(path, HTTP_ORIGIN="http://localhost:5000")
    assert response.status_code == 200, response.data
    assert response.data == [{"id": kept.pk, "filename": "bank letter.pdf", "size": 2048,
                              "uploaded_at": response.data[0]["uploaded_at"], "status": "ready"}]
    assert response.data[0]["uploaded_at"]
    body = response.content.decode()
    assert "finance/" not in body and "staging" not in body and "sha256" not in body
    assert response["Cache-Control"] == "private, no-store"


def test_another_person_cannot_list_someone_elses_payout_files(finance_bundle):
    b = finance_bundle
    document(b, payee(b))
    path = reverse("member-event-payee-file-create", kwargs={"obligation_id": b.obligation.pk})
    assert client_for(b.actor).get(path, HTTP_ORIGIN="http://localhost:5000").status_code == 404
