"""Historical PDFs must remain retryable across the designer migration."""

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import reportlab
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from rest_framework.exceptions import ValidationError

from apps.events import certificate_storage, services_certificates
from apps.events.certificate_rendering import render_certificate_pdf
from apps.events.certificate_templates import DEFAULT_CERTIFICATE_TEMPLATE
from apps.events.models import EventAttendanceCertificate
from apps.events.services_certificate_templates import save_template
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.test_lane_e_designs import response_for


def historical_pdf(certificate):
    """Reference drawing contract from before migration 0030 (Vera + A4)."""
    fonts = Path(reportlab.__file__).parent / "fonts"
    for name, filename in (("CertificateVera", "Vera.ttf"), ("CertificateVeraBold", "VeraBd.ttf")):
        pdfmetrics.registerFont(TTFont(name, fonts / filename))
    output = BytesIO()
    width, height = landscape(A4)
    canvas = Canvas(output, pagesize=(width, height), pageCompression=1, invariant=1)
    canvas.setTitle(f"Attendance certificate {certificate.serial}")
    canvas.setLineWidth(1.5)
    canvas.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm)
    labels = [
        ("CertificateVeraBold", 28, 48, "Certificate of Attendance"),
        ("CertificateVera", 14, 70, "This certifies that"),
        ("CertificateVeraBold", 24, 91, certificate.recipient_name),
        ("CertificateVera", 14, 111, "attended"),
        ("CertificateVeraBold", 20, 130, certificate.event_title),
        ("CertificateVera", 13, 149, certificate.event_starts_at.strftime("%d %B %Y")),
    ]
    for font, size, top, label in labels:
        canvas.setFont(font, size)
        canvas.drawCentredString(width / 2, height - top * mm, label)
    canvas.drawString(22 * mm, 24 * mm, certificate.issuer_name)
    canvas.setFont("CertificateVera", 8)
    canvas.drawRightString(width - 22 * mm, 24 * mm,
                          f"Serial {certificate.serial} \u00b7 Revision {certificate.revision}")
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def test_empty_migration_snapshot_preserves_exact_historical_bytes():
    certificate = SimpleNamespace(
        layout_snapshot={}, recipient_name="Ada Lovelace", event_title="Safety workshop",
        event_starts_at=datetime(2026, 1, 15, tzinfo=timezone.utc), issuer_name="Makerspace",
        serial="00000000-0000-0000-0000-000000000001", revision=1,
    )
    assert render_certificate_pdf(certificate) == historical_pdf(certificate)


def test_new_default_snapshot_still_uses_designer_renderer(monkeypatch):
    legacy = Mock(side_effect=AssertionError("New snapshots must use the designer renderer"))
    monkeypatch.setattr("apps.events.certificate_rendering.render_legacy_certificate_pdf", legacy)
    certificate = SimpleNamespace(
        layout_snapshot=deepcopy(DEFAULT_CERTIFICATE_TEMPLATE), recipient_name="Ada Lovelace",
        event_title="Safety workshop", event_starts_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        issuer_name="Makerspace", serial="NEW", revision=1,
    )
    assert render_certificate_pdf(certificate).startswith(b"%PDF")
    legacy.assert_not_called()


@pytest.mark.django_db
def test_pre_migration_promoted_pdf_recovers_after_quota_failure(monkeypatch):
    space, manager, editor, event, grant = grant_fixture()
    response = response_for(event)
    # The migration's default=dict produces this state for historical rows.
    certificate = EventAttendanceCertificate(
        response=response, registration=response.registration, revision=1,
        recipient_name=response.registration.name, event_title=event.title,
        event_starts_at=event.starts_at, event_ends_at=event.ends_at, issuer_name=space.name,
    )
    certificate.object_key = f"event-certificates/{space.pk}/{certificate.serial}.pdf"
    certificate.save()
    original = historical_pdf(certificate)
    storage = Mock()
    storage.get_object.side_effect = lambda **kwargs: {"Body": BytesIO(original)}
    monkeypatch.setattr(certificate_storage, "_client", lambda endpoint: storage)
    quota = Mock(side_effect=[ValidationError("Storage quota exceeded"), None])
    from apps.events.certificates import lifecycle  # the facade re-exports the workflow
    monkeypatch.setattr(lifecycle.limits, "add_storage", quota)
    with pytest.raises(certificate_storage.CertificateStorageUnavailable):
        services_certificates.render_certificate(certificate)
    certificate.refresh_from_db()
    assert certificate.status == "failed" and certificate.sha256 == ""

    space.enabled_features += ["events.certificate_designer"]
    space.save(update_fields=["enabled_features"])
    save_template(event, actor=editor, parameters={"page_width_mm": 320})
    space.enabled_features.remove("events.certificate_designer")
    space.save(update_fields=["enabled_features"])
    recovered = services_certificates.render_certificate(certificate)
    assert recovered.status == "active" and recovered.layout_snapshot == {}
    assert recovered.template_revision_id is None
    assert recovered.size_bytes == len(original)
    assert recovered.sha256 == hashlib.sha256(original).hexdigest()
    assert quota.call_count == 2
    storage.put_object.assert_not_called()
    storage.copy_object.assert_not_called()
