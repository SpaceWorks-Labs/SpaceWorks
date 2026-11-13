"""New downloads use live payment routing without rewriting financial snapshots."""

from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from django.utils import timezone
from pypdf import PdfReader

from apps.makerspaces.models import Makerspace
from apps.payments.document_pdf import render_document_pdf
from apps.payments.documents import issue_bill
from apps.payments.models import Payment, PaymentDocument
from apps.payments.notifications_p2 import render_document
from apps.payments.reconciliation import mark_offline
from apps.payments.services_refunds_offline import record_offline_refund
from tests.payments.test_refunds import paid_deposit
from tests.return_helpers import make_member, make_space, settlement_details

pytestmark = pytest.mark.django_db


def bill(slug):
    space = make_space(slug)
    staff = make_member(slug + "-staff", space)
    payment = paid_deposit(space, staff, status="pending")
    document = issue_bill(payment, actor=staff)
    assert document is not None
    return space, payment, document


def pdf_text(document):
    pdf = render_document_pdf(document)
    assert pdf.startswith(b"%PDF-")
    return "".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


@pytest.mark.parametrize("state", ["archived", "verified", "unverified", "slug"])
def test_bill_render_reloads_current_tenant_and_preserves_issued_snapshot(settings, state):
    settings.PUBLIC_APP_BASE_URL = "https://central.example.test"
    space, payment, document = bill("s4d-live-document")
    snapshot = PaymentDocument.objects.values().get(pk=document.pk)
    old_navigation = document.issuer["payment_navigation"]
    # Keep document.payment/makerspace cached before changing the database.
    assert document.payment.makerspace.pk == space.pk
    if state == "archived":
        Makerspace.objects.filter(pk=space.pk).update(archived_at=timezone.now())
        expected = "https://central.example.test/member/archived"
    elif state in {"verified", "unverified"}:
        Makerspace.objects.filter(pk=space.pk).update(
            frontend_domain="current.example.test", frontend_domain_status="verified" if state == "verified" else "pending")
        expected = ("https://current.example.test/member/payments" if state == "verified"
                    else f"https://central.example.test/m/{space.slug}/member/payments")
    else:
        Makerspace.objects.filter(pk=space.pk).update(slug="s4d-renamed")
        expected = "https://central.example.test/m/s4d-renamed/member/payments"
    text = "".join(pdf_text(document).split())
    assert expected in text
    if expected != old_navigation:
        assert old_navigation not in text
    assert PaymentDocument.objects.values().get(pk=document.pk) == snapshot
    assert payment.status == "pending"


def test_imported_bill_uses_target_payment_tenant_and_keeps_source_financial_snapshot(settings):
    settings.PUBLIC_APP_BASE_URL = "https://target.example.test"
    _source_space, _source_payment, source = bill("s4d-source")
    target = make_space("s4d-imported")
    target_staff = make_member("s4d-imported-staff", target)
    payment = paid_deposit(target, target_staff, status="pending", intent="pi_imported")
    # Import remaps relational IDs while retaining the immutable issuer/line snapshots.
    imported = PaymentDocument.objects.create(
        makerspace=target, payment=payment, sequence=source.sequence, number=source.number,
        kind=source.kind, issuer=deepcopy(source.issuer), payer_label=source.payer_label,
        payer_type=source.payer_type, lines=deepcopy(source.lines), amount=source.amount,
        currency=source.currency, money_at=source.money_at,
    )
    before = PaymentDocument.objects.values().get(pk=imported.pk)
    text = "".join(pdf_text(imported).split())
    assert "https://target.example.test/m/s4d-imported/member/payments" in text
    assert source.issuer["payment_navigation"] not in text
    assert imported.issuer == source.issuer
    assert PaymentDocument.objects.values().get(pk=imported.pk) == before


def test_bill_uses_current_routing_tenant_including_its_archival(settings):
    settings.PUBLIC_APP_BASE_URL = "https://central.example.test"
    _owner, payment, document = bill("s4d-owner")
    via = make_space("s4d-routing")
    Payment.objects.filter(pk=payment.pk).update(via_makerspace=via)
    assert "https://central.example.test/m/s4d-routing/member/payments" in "".join(pdf_text(document).split())
    Makerspace.objects.filter(pk=via.pk).update(archived_at=timezone.now())
    assert "https://central.example.test/member/archived" in "".join(pdf_text(document).split())


@pytest.mark.parametrize("kind", ["bill", "receipt", "credit_note"])
@pytest.mark.parametrize("state", ["archived", "verified"])
def test_document_email_and_chat_captions_reload_live_navigation(settings, kind, state):
    settings.PUBLIC_APP_BASE_URL = "https://central.example.test"
    space, payment, document = bill("s4d-caption")
    stale_navigation = document.issuer["payment_navigation"]
    if kind != "bill":
        mark_offline(payment, payment.created_by, settlement_details())
        document = PaymentDocument.objects.get(payment=payment, kind="receipt")
        if kind == "credit_note":
            refund = record_offline_refund(payment, amount="2.00", reason="Returned", actor=payment.created_by,
                receipt={"method": "cash", "reference": "s4d-caption", "refunded_at": timezone.now()})
            document = PaymentDocument.objects.get(refund=refund)
    if state == "archived":
        Makerspace.objects.filter(pk=space.pk).update(archived_at=timezone.now())
        expected = "https://central.example.test/member/archived"
    else:
        Makerspace.objects.filter(pk=space.pk).update(
            frontend_domain="caption.example.test", frontend_domain_status="verified")
        expected = "https://caption.example.test/member"
    rendered = render_document(SimpleNamespace(makerspace_id=space.pk, source_id=document.pk))
    assert expected in rendered["text"] and expected in rendered["html"]
    assert rendered["link"] == urlsplit(expected).path
    assert stale_navigation not in rendered["text"]
