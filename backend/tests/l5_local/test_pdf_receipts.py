"""Owner decision #155: ledger receipts may be PDFs; issue/return evidence stays images-only."""

from io import BytesIO

import pytest

from apps.evidence import image_validation, storage
from apps.evidence.storage import validate_evidence_object as REAL_VALIDATE  # before conftest's fake
from apps.evidence.models import EvidencePhoto
from apps.payments import ledger_api
from apps.payments.exceptions_ledger import LedgerConflict
from tests.l5_local.helpers import client, setup

PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << >>\n%%EOF\n"


class FakeS3:
    def __init__(self, data):
        self.data = data

    def head_object(self, **_kw):
        return {"ContentLength": len(self.data), "VersionId": "v1"}

    def get_object(self, **_kw):
        return {"Body": BytesIO(self.data)}


def test_pdf_is_detected_only_for_receipt_keys():
    assert image_validation.detect_mime_for_key("evidence/7/receipt/abc", PDF) == "application/pdf"
    assert image_validation.detect_mime_for_key("staging/evidence/7/receipt/abc", PDF) == "application/pdf"
    assert image_validation.detect_mime_for_key("evidence/7/issue/abc", PDF) is None
    assert "application/pdf" in image_validation.allowed_mime_for_key("evidence/7/receipt/a", ("image/jpeg",))
    assert "application/pdf" not in image_validation.allowed_mime_for_key("evidence/7/return/a", ("image/jpeg",))


def test_storage_accepts_a_pdf_receipt_and_refuses_a_pdf_as_handover_evidence(monkeypatch):
    monkeypatch.setattr(storage, "_client", lambda: FakeS3(PDF))
    monkeypatch.setattr(storage, "checkpoint", lambda: None)
    assert REAL_VALIDATE("evidence/7/receipt/abc").content_type == "application/pdf"
    for kind in ("issue", "return"):
        with pytest.raises(storage.EvidenceObjectValidationError):
            REAL_VALIDATE(f"evidence/7/{kind}/abc")


@pytest.mark.django_db
def test_ledger_entry_takes_a_pdf_receipt_and_refuses_a_type_mismatch(monkeypatch):
    space, manager, _payer = setup("pdf-receipt", "finance.ledger")

    def photo(content_type):
        return EvidencePhoto.objects.create(makerspace=space, evidence_type="receipt",
                                            object_key=f"evidence/{space.pk}/receipt/{EvidencePhoto.objects.count()}",
                                            content_type=content_type, uploaded_by=manager)

    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
                        lambda evidence, max_bytes: storage.EvidenceValidationResult(size=len(PDF),
                                                                                     content_type="application/pdf"))
    monkeypatch.setattr("apps.evidence.finalization.charge_storage_once", lambda evidence, size: None)
    entry = ledger_api.record_expense(space, "general", None, "10.00", "usd", "cash", "", photo("application/pdf"),
                                      "manual", "", manager, category="rent")
    assert entry.receipt.content_type == "application/pdf"
    entry.receipt.refresh_from_db()
    assert entry.receipt.consumption_state == "consumed"
    row = client(manager).get(f"/api/v1/admin/makerspace/{space.pk}/finance/entries").json()["results"][0]
    assert row["receipt_kind"] == "pdf"
    with pytest.raises(LedgerConflict) as exc:
        ledger_api.record_expense(space, "general", None, "11.00", "usd", "cash", "", photo("image/jpeg"),
                                  "manual", "", manager, category="rent")
    assert exc.value.detail["code"] == "receipt_type_mismatch"


@pytest.mark.django_db
def test_presign_accepts_pdf_for_receipts_but_staff_evidence_upload_does_not(monkeypatch):
    space, manager, _payer = setup("pdf-presign", "finance.ledger")
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload",
                        lambda key, content_type: {"url": "https://s3.test/up", "fields": {"Content-Type": content_type}})
    api = client(manager)
    ok = api.post(f"/api/v1/admin/makerspace/{space.pk}/finance/receipt-upload",
                  {"content_type": "application/pdf", "size_bytes": 2048}, format="json")
    assert ok.status_code == 201
    assert EvidencePhoto.objects.get(pk=ok.json()["evidence_id"]).evidence_type == "receipt"
    from apps.evidence.serializers import EvidenceUrlRequestSerializer

    for kind in ("issue", "return"):
        assert not EvidenceUrlRequestSerializer(data={"evidence_type": kind, "content_type": "application/pdf"}).is_valid()
    assert not EvidencePhoto.objects.filter(makerspace=space, evidence_type="issue").exists()
