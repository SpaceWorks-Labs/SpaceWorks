"""Native owners redeem signed PDF grants through real device authentication."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.payments.models import PaymentDocument
from tests.accounts.native_helpers_m1d import attested_login
from tests.accounts.test_native_staff_surface_m1a import bearer
from tests.payments.test_documents import settled

pytestmark = pytest.mark.django_db


def test_native_payer_download_rechecks_signature_owner_and_current_access(settings, monkeypatch):
    space, _, payment = settled("fg-native-pdf")
    owner = payment.member
    owner.set_password("strong-device-password")
    owner.save(update_fields=["password"])
    login, _ = attested_login(APIClient(), owner, settings, monkeypatch)
    assert login.status_code == 200, login.data
    client = bearer(login.data["access"])
    document = PaymentDocument.objects.get(payment=payment)
    path = reverse("member-payment-document-url", args=[space.pk, document.pk])
    result = client.get(path)
    assert result.status_code == 200, result.data
    grant = result.data["url"]
    monkeypatch.setattr("apps.payments.document_pdf.render_document_pdf", lambda row: b"%PDF-native-test")
    downloaded = client.get(grant)
    assert downloaded.status_code == 200 and downloaded.content == b"%PDF-native-test"
    assert downloaded["Cache-Control"] == "private, no-store"
    assert client.get(grant + "tampered").status_code == 400
    # The same native token cannot enter an ordinary delegated staff route.
    assert client.get(f"/api/v1/admin/makerspace/{space.pk}/analytics/summary").status_code == 403
    from tests.return_helpers import authenticated_client, make_user
    assert authenticated_client(make_user("fg-not-payer")).get(grant).status_code == 403
    from tests.accounts.account_factories import make_membership
    member = make_membership(owner, space)
    member.status = "revoked"
    member.save(update_fields=["status"])
    assert client.get(grant).status_code == 403
