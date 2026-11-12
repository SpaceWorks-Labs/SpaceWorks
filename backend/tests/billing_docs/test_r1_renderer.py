"""Branding snapshots, logo retention, legacy inputs and bounded PDF delivery."""

from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from apps.payments.document_pdf import render_document_pdf, DocumentRenderError
from apps.payments.document_pdf_assets import retain_logo, load_logo
from apps.payments.document_snapshot import issuer_snapshot
from apps.payments.documents import issue_bill
from apps.payments.models import MakerspaceBillingSettings, PaymentDocument
from tests.billing_docs.test_r1_bills import pending

pytestmark = pytest.mark.django_db


def legacy_document():
    return SimpleNamespace(pk=1, kind="receipt", get_kind_display=lambda: "Receipt",
        issuer={"name": "Legacy issuer", "address": "Old address", "footer": "Thank you"},
        number="OLD-000001", issued_at=datetime(2026, 10, 16, 20, tzinfo=timezone.utc),
        money_at=datetime(2026, 10, 16, 20, tzinfo=timezone.utc), payer_label="payer",
        lines=[{"label": "Charge", "quantity": "1", "unit_amount": "10.00", "total": "10.00"}],
        amount="10.00", currency="usd", settlement_method="cash", settlement_reference="cash-1",
        reverses_id=None, branding_logo_key="", branding_logo_sha256="", tax_breakdown=None)


def png(colour="red", size=(1200, 600)):
    output = BytesIO()
    Image.new("RGB", size, colour).save(output, "PNG")
    return output.getvalue()


class MemoryStore:
    def __init__(self):
        self.objects = {}

    def get_object(self, *, Bucket, Key):
        data = self.objects[(Bucket, Key)]
        return {"Body": BytesIO(data), "ContentLength": len(data)}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.objects.setdefault((Bucket, Key), Body)


def test_retained_logo_survives_source_replacement_and_target_key_rewrite(monkeypatch, settings):
    from apps.makerspaces.storage_key_collectors import collect_private_object_keys
    from apps.tenant_migration.object_fields import rewrite_object_fields
    space, _, payment = pending("r1-logo")
    store = MemoryStore()
    monkeypatch.setattr("apps.payments.document_pdf_assets._client", lambda: store)
    space.logo_key = "public/logo.png"
    space.save(update_fields=["logo_key"])
    store.objects[(settings.PUBLIC_IMAGE_BUCKET, space.logo_key)] = png()
    bill = issue_bill(payment)
    assert bill.branding_logo_key.startswith(f"billing-branding/{space.pk}/")
    original = load_logo(bill)
    assert original and len(original) <= 256 * 1024
    with Image.open(BytesIO(original)) as image:
        assert image.width <= 600 and image.height <= 300
    store.objects[(settings.PUBLIC_IMAGE_BUCKET, space.logo_key)] = png("blue")
    new_key, new_digest = retain_logo(space)
    assert new_key != bill.branding_logo_key and new_digest != bill.branding_logo_sha256
    del store.objects[(settings.PUBLIC_IMAGE_BUCKET, space.logo_key)]
    assert load_logo(bill) == original
    assert bill.branding_logo_key in collect_private_object_keys(space, include_coordination=False)
    target_key = "tenant-import/target/private/retained-logo.png"
    row = {"branding_logo_key": bill.branding_logo_key, "branding_logo_sha256": bill.branding_logo_sha256}
    rewrite_object_fields(PaymentDocument, row, {bill.branding_logo_key: target_key})
    store.objects[(settings.AWS_STORAGE_BUCKET_NAME, target_key)] = original
    bill.branding_logo_key = row["branding_logo_key"]
    assert load_logo(bill) == original and row["branding_logo_sha256"] == bill.branding_logo_sha256


def test_logo_storage_failure_and_digest_mismatch_render_without_logo(monkeypatch):
    space, _, payment = pending("r1-logo-failure")
    space.logo_key = "missing.png"
    monkeypatch.setattr("apps.payments.document_pdf_assets._client", lambda: MemoryStore())
    assert retain_logo(space) == ("", "")
    document = legacy_document()
    document.branding_logo_key, document.branding_logo_sha256 = "missing", "0" * 64
    assert render_document_pdf(document).startswith(b"%PDF-")


def test_snapshots_capture_accent_timezone_contact_due_instructions_and_via_navigation():
    space, _, payment = pending("r1-snapshot")
    space.timezone = "Asia/Kolkata"
    space.theme_config = {"accent_color": "#123456"}
    space.branding_config = {"support_email": "billing@example.com"}
    # Service re-fetches its locked payment; persist these branding inputs.
    space.save(update_fields=["timezone", "theme_config", "branding_config"])
    policy = MakerspaceBillingSettings.objects.create(makerspace=space, payment_instructions="Pay at the desk")
    bill = issue_bill(payment)
    assert bill.issuer["accent_color"] == "#123456"
    assert bill.issuer["timezone"] == "Asia/Kolkata"
    assert bill.issuer["contact_email"] == "billing@example.com"
    assert bill.issuer["payment_instructions"] == "Pay at the desk"
    assert bill.issuer["payment_navigation"].endswith(f"/m/{space.slug}/member/payments")
    space.theme_config = {"accent_color": "invalid"}
    payment.makerspace = space
    assert issuer_snapshot(payment, policy, "bill")["accent_color"] != "invalid"
    bill.refresh_from_db()
    assert bill.issuer["accent_color"] == "#123456"
    from tests.return_helpers import make_space
    visiting_space = make_space("r1-snapshot-visiting")
    payment.via_makerspace = visiting_space
    assert issuer_snapshot(payment, policy, "bill")["payment_navigation"].endswith(
        f"/m/{visiting_space.slug}/member/payments")


def test_bill_renderer_uses_live_status_and_never_offers_an_unavailable_online_rail(monkeypatch):
    from pypdf import PdfReader
    from apps.payments.models import Payment
    _, _, payment = pending("r1-render-status")
    document = issue_bill(payment)
    monkeypatch.setattr("apps.payments.availability.online_payments_enabled_for", lambda _: False)
    def extracted():
        return "\n".join(page.extract_text() for page in PdfReader(BytesIO(render_document_pdf(document))).pages)
    first = extracted()
    assert "Unpaid" in first and "Pay online" not in first
    monkeypatch.setattr("apps.payments.availability.online_payments_enabled_for", lambda _: True)
    assert "Pay online" in extracted()
    Payment.objects.filter(pk=payment.pk).update(status="waived")
    assert "Waived" in extracted() and "Pay online" not in extracted()


def test_legacy_renderer_is_deterministic_for_identical_complete_inputs():
    document = legacy_document()
    assert render_document_pdf(document) == render_document_pdf(document)


def test_worst_case_200_lines_logo_and_mixed_scripts_is_under_one_megabyte(monkeypatch):
    document = legacy_document()
    from apps.payments.document_pdf_assets import normalize_logo
    monkeypatch.setattr("apps.payments.document_pdf_assets.load_logo", lambda _: normalize_logo(png()))
    mixed = "Zoë Ελληνικά العربية हिन्दी বাংলা தமிழ் ខ្មែរ မြန်မာ 中文 日本語 한국어"
    document.lines = [{"label": mixed, "quantity": "1", "unit_amount": "1.00", "total": "1.00"}] * 200
    document.amount = "200.00"
    payload = render_document_pdf(document)
    assert len(payload) < 1024 * 1024


def test_render_over_hard_cap_is_failure_instead_of_a_link_only_result(monkeypatch):
    monkeypatch.setattr("apps.payments.document_pdf._render", lambda _: b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(DocumentRenderError):
        render_document_pdf(legacy_document())


def test_webp_logo_is_accepted_and_normalised_to_png():
    """Review r5/r6: every allowed public-image logo format reaches the retained branding snapshot."""
    from PIL import Image
    from apps.payments.document_pdf_assets import normalize_logo
    source = BytesIO()
    Image.new("RGB", (1200, 400), (12, 34, 56)).save(source, format="WEBP")
    normalised = normalize_logo(source.getvalue())
    with Image.open(BytesIO(normalised)) as image:
        assert image.format == "PNG" and image.width <= 600 and image.height <= 300
