"""Real mounted routes + staging object upload; run only in the isolated local harness.

No upload, scanner, permissions, workflow or core-ledger provider is replaced.
Requires G's mounts/migrations and B's completed transport/recovery entrypoint.
"""
from datetime import timedelta
from uuid import UUID, uuid4
import pytest
import requests
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts import reauthentication
from apps.events.services_checkin import mark_attended_with_event
from apps.event_reimbursements.models import ReimbursementClaim
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from tests.accounts.test_reauthentication import request as session_request, PASSWORD
from .helpers import accepted, decision_data
from .conftest import cmd

pytestmark = pytest.mark.django_db(transaction=True)


def pdf_receipt():
    """A small valid PDF, with correct xref offsets, generated without a decoder double."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    content = b'BT /F1 12 Tf 10 150 Td (Rail travel receipt INR 100.00) Tj ET'
    objects.append(b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'\nendstream')
    output, offsets = bytearray(b'%PDF-1.4\n'), [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(output)); output.extend(f'{index} 0 obj\n'.encode() + value + b'\nendobj\n')
    start = len(output)
    output.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        output.extend(f'{offset:010} 00000 n \n'.encode())
    output.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    return bytes(output)


def send(client, method, name, kwargs, data):
    return getattr(client, method)(reverse(name, kwargs=kwargs), data, format="json",
        HTTP_IDEMPOTENCY_KEY=str(data["operation_id"]), HTTP_ORIGIN="http://localhost:5000")


@pytest.mark.parametrize("hackathon", [False, True], ids=["ordinary", "hackathon"])
def test_actual_receipt_upload_submit_and_finance_decision(make_world, monkeypatch, settings, hackathon):
    settings.AWS_S3_PUBLIC_ENDPOINT_URL = settings.AWS_S3_ENDPOINT_URL
    world = make_world(hackathon=hackathon)
    award = accepted(world)
    monkeypatch.setattr(timezone, "now", lambda: world.event.starts_at + timedelta(hours=1))
    mark_attended_with_event(award.request.registration, actor=world.manager, source="qr")
    monkeypatch.setattr(timezone, "now", lambda: world.event.ends_at + timedelta(days=1))
    owner_session = session_request(world.owner, surface="member")
    client = APIClient(); client.force_authenticate(world.owner, token=owner_session.auth)
    member = {"makerspace_id": world.space.pk, "pk": world.event.pk}
    response = send(client, "put", "member-event-reimbursement-claim", member, cmd(lines=[]))
    assert response.status_code == 200, response.data
    claim = ReimbursementClaim.objects.get(pk=response.data["id"])
    pdf = pdf_receipt()
    response = send(client, "post", "member-event-receipt-file-create", member, cmd(claim_uuid=str(claim.uuid),
        question_id="receipt", filename="receipt.pdf", bytes=len(pdf), mime="application/pdf"))
    assert response.status_code == 201, response.data
    asset_id, generation, upload = response.data["asset_id"], response.data["generation"], response.data["upload"]
    if upload["method"] == "POST":
        result = requests.post(upload["url"], data=upload["fields"], files={"file": ("receipt.pdf", pdf, "application/pdf")}, timeout=20)
    else:
        assert upload["method"] == "PUT"
        result = requests.put(upload["url"], data=pdf, headers={"Content-Type": "application/pdf"}, timeout=20)
    assert result.status_code in (200, 204)
    asset_kwargs = {**member, "asset_id": asset_id}
    metadata = client.get(reverse("member-event-receipt-file-detail", kwargs=asset_kwargs)).data
    response = send(client, "post", "member-event-receipt-file-complete", asset_kwargs,
        cmd(metadata["version"], generation=generation))
    assert response.status_code == 202, response.data
    from apps.payments.event_payouts.tasks import recover_finance_work_task
    recover_finance_work_task()
    metadata = client.get(reverse("member-event-receipt-file-detail", kwargs=asset_kwargs)).data
    assert metadata["state"] == "ready", metadata
    assert metadata["sha256"] and not {"url", "object_key", "staging_key"} & metadata.keys()
    line_id = uuid4()
    claim.refresh_from_db()
    line = {"line_uuid": str(line_id), "category": "rail", "vendor": "Rail vendor", "traveller": "Maker", "description": "Travel",
        "expense_date": world.event.starts_at.date().isoformat(), "original_amount_minor": 10000, "original_currency": "INR",
        "fx_rate": "1", "rate_date": world.event.starts_at.date().isoformat(), "rate_source": "receipt",
        "route": {"mode": "rail", "origin": "Kochi", "destination": "Bengaluru"},
        "receipt": {"asset_id": asset_id, "generation": generation, "sha256": metadata["sha256"], "receipt_total_minor": 10000}}
    response = send(client, "put", "member-event-reimbursement-claim", member, cmd(claim.version, lines=[line]))
    assert response.status_code == 200, response.data
    response = send(client, "post", "member-event-reimbursement-claim-submit", member,
        cmd(response.data["version"], current_revision=None))
    assert response.status_code == 200, response.data
    world.finance = session_request(world.manager)
    reauthentication.verify(world.finance, password=PASSWORD)
    client.force_authenticate(world.manager, token=world.finance.auth)
    decision = decision_data(world, claim, line_id, 9000, outcome="partially_approved")
    response = send(client, "post", "admin-event-reimbursement-claim-review", {"pk": world.event.pk, "claim_id": claim.pk}, decision)
    assert response.status_code == 200, response.data
    obligation = EventPayoutObligation.objects.get(source_uuid=claim.uuid)
    assert obligation.approved_minor == 9000 and not obligation.entries.exists()
