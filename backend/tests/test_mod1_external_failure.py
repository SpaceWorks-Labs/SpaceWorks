"""MOD-1 condition 6: mail transport down while staff decide a request -- the decision stands, nothing half-written."""
import smtplib

import pytest
from django.test import override_settings

from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from tests.return_helpers import authenticated_client, make_member, make_product, make_space
from tests.p3_fixbe_helpers import prove_owner_mailbox
from tests.test_request_workflow import accept_url, make_hardware_request, reject_url

pytestmark = pytest.mark.django_db


@pytest.fixture
def smtp_down(monkeypatch):
    calls = []

    def boom(self, messages):
        calls.append(len(messages))
        raise smtplib.SMTPServerDisconnected("connection refused")

    monkeypatch.setattr("django.core.mail.backends.locmem.EmailBackend.send_messages", boom)
    return calls


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_accept_with_mail_down_still_accepts_reserves_stock_and_audits(django_capture_on_commit_callbacks, smtp_down):
    space = make_space("m1-ext-accept")
    product = make_product(space, total_quantity=5, available_quantity=5)
    request = make_hardware_request(space, product, quantity=2, contact_email="who@example.com")
    prove_owner_mailbox(request)
    admin = make_member("m1-ext-accept-admin", space)

    with django_capture_on_commit_callbacks(execute=True):
        response = authenticated_client(admin).post(accept_url(request), format="json")

    assert response.status_code == 200
    assert response.data["status"] == HardwareRequest.Status.ACCEPTED
    request.refresh_from_db(); product.refresh_from_db()
    assert request.status == HardwareRequest.Status.ACCEPTED
    assert (product.available_quantity, product.reserved_quantity) == (3, 2)
    assert AuditLog.objects.filter(action="request.accepted", target_id=str(request.pk)).count() == 1


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_reject_with_mail_down_still_rejects_and_keeps_the_reason(django_capture_on_commit_callbacks, smtp_down):
    space = make_space("m1-ext-reject")
    product = make_product(space)
    request = make_hardware_request(space, product, contact_email="who2@example.com")
    prove_owner_mailbox(request)
    admin = make_member("m1-ext-reject-admin", space)

    with django_capture_on_commit_callbacks(execute=True):
        response = authenticated_client(admin).post(reject_url(request), {"reason": "No stock."}, format="json")

    assert response.status_code == 200
    request.refresh_from_db()
    assert (request.status, request.rejection_reason) == (HardwareRequest.Status.REJECTED, "No stock.")
    assert AuditLog.objects.filter(action="request.rejected", target_id=str(request.pk)).count() == 1
