"""Security level: upload validation, webhook signatures, and no secrets in logs.

Exact outcomes, not "not a 5xx": each refusal asserts its status and what must NOT have been written.
"""
import logging
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.evidence.models import EvidencePhoto
from apps.payments.models import Payment
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db


# --- evidence upload validation ---------------------------------------------------------------------------


@pytest.fixture
def uploader(monkeypatch):
    space = make_space("lvl-upload")
    presign = Mock(return_value={"url": "https://storage.test/up", "fields": {"key": "k"}})
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload", presign)
    return space, authenticated_client(make_member("lvl-upload-staff", space)), presign


def _url(space):
    return reverse("evidence_admin:evidence-upload-url", kwargs={"makerspace_id": space.pk})


@pytest.mark.parametrize("mime", ["image/svg+xml", "text/html", "application/pdf", "image/gif", "application/x-php",
                                  "IMAGE/PNG", "image/png; charset=x", "", "../../etc/passwd"])
def test_a_content_type_outside_the_allow_list_is_refused_before_anything_is_signed(uploader, mime):
    space, client, presign = uploader
    response = client.post(_url(space), {"evidence_type": "issue", "content_type": mime}, format="json")
    assert response.status_code == 400
    assert "content_type" in response.data
    presign.assert_not_called()
    assert not EvidencePhoto.objects.filter(makerspace=space).exists()


def test_an_unknown_evidence_type_is_refused(uploader):
    space, client, presign = uploader
    response = client.post(_url(space), {"evidence_type": "avatar", "content_type": "image/png"}, format="json")
    assert response.status_code == 400 and "evidence_type" in response.data
    presign.assert_not_called()


@pytest.mark.parametrize("mime", settings.EVIDENCE_ALLOWED_MIME)
def test_every_allowed_type_is_signed_on_the_staging_key_only(uploader, mime):
    space, client, presign = uploader
    response = client.post(_url(space), {"evidence_type": "issue", "content_type": mime, "size_bytes": 1000}, format="json")
    assert response.status_code == 201, response.data
    photo = EvidencePhoto.objects.get(pk=response.data["evidence_id"])
    presign.assert_called_once_with(photo.object_key, mime)
    assert AuditLog.objects.filter(action="evidence.upload_url_issued", makerspace=space).count() == 1


def test_a_negative_size_is_refused(uploader):
    space, client, presign = uploader
    response = client.post(_url(space), {"evidence_type": "issue", "content_type": "image/png", "size_bytes": -1}, format="json")
    assert response.status_code == 400 and "size_bytes" in response.data
    presign.assert_not_called()


def test_another_makerspace_cannot_request_an_upload_here(uploader):
    space, _client, presign = uploader
    other = make_space("lvl-upload-other")
    outsider = authenticated_client(make_member("lvl-upload-outsider", other))
    response = outsider.post(_url(space), {"evidence_type": "issue", "content_type": "image/png"}, format="json")
    assert (response.status_code, response.json()["code"]) == (404, "not_found")  # 481(1): as if missing
    presign.assert_not_called()
    assert not EvidencePhoto.objects.filter(makerspace=space).exists()


# --- webhook signatures -----------------------------------------------------------------------------------

WEBHOOKS = [
    ("/api/v1/webhooks/stripe/connect", "HTTP_STRIPE_SIGNATURE"),
    ("/api/v1/webhooks/stripe/zzunknown", "HTTP_STRIPE_SIGNATURE"),
    ("/api/v1/webhooks/razorpay/zzunknown", "HTTP_X_RAZORPAY_SIGNATURE"),
]


@pytest.mark.parametrize("url,header", WEBHOOKS)
@pytest.mark.parametrize("signature", [None, "", "garbage", "t=1,v1=deadbeef", "sha256=00"])
def test_a_webhook_with_no_or_a_bad_signature_changes_nothing(url, header, signature):
    payments, audits = Payment.objects.count(), AuditLog.objects.count()
    extra = {header: signature} if signature is not None else {}
    response = APIClient(raise_request_exception=False).post(
        url, data=b'{"type":"payment_intent.succeeded","data":{"object":{"id":"pi_x"}}}',
        content_type="application/json", **extra)
    assert response.status_code in (400, 401, 403, 404), response.status_code
    assert Payment.objects.count() == payments
    assert AuditLog.objects.count() == audits


# --- no secrets in logs -----------------------------------------------------------------------------------


def test_a_failed_sign_in_logs_neither_the_password_nor_the_token(caplog):
    make_user("lvl-log-user", password="Correct-horse-9!")
    secret = "Wr0ng-Passw0rd-leak-canary"
    with caplog.at_level(logging.DEBUG):
        response = APIClient().post("/api/v1/auth/login", {"username": "lvl-log-user", "password": secret}, format="json")
    assert response.status_code in (400, 401, 403)
    assert secret not in caplog.text
    assert "Correct-horse-9!" not in caplog.text


def test_a_failed_password_reset_logs_no_token(caplog):
    canary = "reset-token-leak-canary-123"
    with caplog.at_level(logging.DEBUG):
        APIClient().post("/api/v1/auth/reset-password", {"token": canary, "password": "N3w-Passw0rd-canary!"}, format="json")
    assert canary not in caplog.text and "N3w-Passw0rd-canary!" not in caplog.text
