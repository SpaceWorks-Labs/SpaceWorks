"""MOD-1B: evidence content sniffing (the MIME decision is made from bytes, never the client's claim) and the two beat tasks.

Only the `receipt` evidence type may hold a PDF; issue and return evidence stay images-only (owner decision #155).
"""

from io import BytesIO

import pytest
from PIL import Image

from apps.evidence.image_validation import (
    allowed_mime_for_key,
    detect_mime_for_key,
    image_mime_from_bytes,
    is_receipt_key,
    pdf_mime_from_bytes,
)

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"


def encoded(fmt, size=(2, 2)):
    buffer = BytesIO()
    Image.new("RGB", size, (200, 10, 10)).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.mark.parametrize("fmt, mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_the_three_allowed_image_formats_are_recognised_from_their_bytes(fmt, mime):
    assert image_mime_from_bytes(encoded(fmt)) == mime


@pytest.mark.parametrize("data", [
    b"", b"\x00" * 64, b"GIF89a" + b"\x00" * 32, b"<script>alert(1)</script>", PDF, b"\xff\xd8\xff" + b"\x00" * 8,
])
def test_anything_else_is_not_an_image(data):
    assert image_mime_from_bytes(data) is None


def test_a_truncated_image_is_refused_not_trusted_for_its_header():
    good = encoded("PNG", size=(40, 40))
    assert image_mime_from_bytes(good[: len(good) // 2]) is None


def test_a_gif_is_a_real_image_but_not_an_allowed_evidence_format():
    buffer = BytesIO()
    Image.new("P", (2, 2)).save(buffer, format="GIF")
    assert image_mime_from_bytes(buffer.getvalue()) is None


@pytest.mark.parametrize("key, receipt", [
    ("evidence/7/receipt/abc", True), ("staging/evidence/7/receipt/abc", True),
    ("evidence/7/issue/abc", False), ("evidence/7/return/abc", False), ("staging/evidence/7/issue/abc", False),
    ("evidence/7/receipt", False), ("other/7/receipt/abc", False), ("", False), (None, False),
])
def test_only_a_receipt_key_is_a_receipt(key, receipt):
    assert is_receipt_key(key) is receipt


def test_a_pdf_needs_the_header_first_and_the_end_marker_near_the_end():
    assert pdf_mime_from_bytes(PDF) == "application/pdf"
    assert pdf_mime_from_bytes(b"x" + PDF) is None
    assert pdf_mime_from_bytes(b"%PDF-1.4\nbody without a terminator") is None
    assert pdf_mime_from_bytes(b"%PDF-1.4\n%%EOF\n" + b"\x00" * 3000) is None  # marker outside the last 2 KiB
    assert pdf_mime_from_bytes(b"%PDF-1.4\n" + b"\x00" * 3000 + b"%%EOF") == "application/pdf"


def test_a_pdf_is_detected_for_a_receipt_key_and_refused_for_issue_and_return_keys():
    assert detect_mime_for_key("evidence/7/receipt/abc", PDF) == "application/pdf"
    assert detect_mime_for_key("staging/evidence/7/receipt/abc", PDF) == "application/pdf"
    assert detect_mime_for_key("evidence/7/issue/abc", PDF) is None
    assert detect_mime_for_key("evidence/7/return/abc", PDF) is None


def test_an_image_wins_over_the_pdf_check_and_garbage_is_refused_for_every_key():
    assert detect_mime_for_key("evidence/7/receipt/abc", encoded("JPEG")) == "image/jpeg"
    assert detect_mime_for_key("evidence/7/issue/abc", encoded("PNG")) == "image/png"
    assert detect_mime_for_key("evidence/7/receipt/abc", b"not a file") is None


def test_allowed_mime_adds_pdf_for_receipts_only():
    images = ["image/jpeg", "image/png"]
    assert allowed_mime_for_key("evidence/7/issue/abc", images) == ("image/jpeg", "image/png")
    assert allowed_mime_for_key("evidence/7/receipt/abc", images) == ("image/jpeg", "image/png", "application/pdf")


@pytest.mark.django_db
def test_the_beat_tasks_pass_dry_run_and_batch_size_through_and_return_their_summaries(monkeypatch, settings):
    from apps.evidence import tasks

    calls = {}
    monkeypatch.setattr(tasks, "sweep_evidence_retention",
                        lambda dry_run, batch_size: calls.setdefault("sweep", (dry_run, batch_size)) and {"swept": True})
    assert tasks.sweep_evidence_retention_task(dry_run=1, batch_size=5) == {"swept": True}
    assert calls["sweep"] == (True, 5)

    order = []
    monkeypatch.setattr(tasks, "reconcile_receipts", lambda dry_run, batch_size: order.append("reconcile") or {"r": dry_run})
    monkeypatch.setattr(tasks, "sweep_abandoned_evidence_uploads", lambda dry_run, batch_size: order.append("cleanup") or {"c": batch_size})
    result = tasks.cleanup_abandoned_evidence_uploads_task(dry_run=0, batch_size=9)
    assert order == ["reconcile", "cleanup"]  # receipts are reconciled FIRST, whatever the cleanup switches say
    assert result == {"reconciliation": {"r": False}, "cleanup": {"c": 9}}
