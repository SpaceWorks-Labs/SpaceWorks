"""Canonical source intents and reviewed addressed variables travel together."""
from types import SimpleNamespace

import pytest
from django.db import transaction

from apps.hardware_requests.notification_projection import addressed_context
from apps.hardware_requests.notifications_p2 import fanout
from apps.integrations.models_contract import NotificationEnvelope
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def test_projection_excludes_contacts_free_text_and_credentials():
    space = SimpleNamespace(name="Workshop")
    context = {"request": SimpleNamespace(id=42, status="issued", return_due_at=None,
               contact_email="private@example.com", remarks="private notes"),
               "status_url": "https://example.com/?token=secret", "secret": "hidden"}
    projected = addressed_context(space, "hardware_requests", "issued", "requester", context)
    assert projected["makerspace.name"] == "Workshop"
    assert projected["request.id"] == 42
    assert projected["request.status"] == "issued"
    assert "private" not in str(projected) and "secret" not in str(projected)
    assert addressed_context(space, "hardware_requests", "unknown", "requester", context) == {}


def test_repeated_source_revision_creates_one_personal_intent_without_inbox(monkeypatch):
    space = make_space("recon-source-intent")
    space.enabled_modules = [key for key in space.enabled_modules if key != "notifications"]
    space.save(update_fields=["enabled_modules"])
    user = make_user("recon-source-owner", access_status="active")
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    values = dict(space=space, feature="hardware_requests", stream="hardware", event="back_available",
                  kind="inventory.watch", source="42", version="1", subject=space, owner=user,
                  own={"subject": "Available", "text": "An item is available."}, rooms=False)
    for _ in range(2):
        assert fanout(**values).scheduled
    row = NotificationEnvelope.objects.get(recipient=user)
    assert row.source_kind == "inventory.watch"
    assert row.context == {"makerspace.name": space.name}
    from apps.notifications.models_inbox import NotificationInboxRow
    assert not NotificationInboxRow.objects.filter(user=user).exists()


def test_rollback_removes_source_intent_and_its_enqueue(monkeypatch, django_capture_on_commit_callbacks):
    space, user = make_space("recon-source-rollback"), make_user("recon-source-rollback", access_status="active")
    queued = []
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", queued.append)
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            fanout(space=space, feature="hardware_requests", stream="hardware", event="back_available",
                   kind="inventory.watch", source="42", version="1", subject=space,
                   owner=user, own={"text": "Available"}, rooms=False)
            raise RuntimeError("domain transaction rolled back")
    assert not NotificationEnvelope.objects.filter(recipient=user).exists()
    assert queued == []


def test_charge_summary_requires_the_same_tenant_loan_subject(monkeypatch):
    from apps.hardware_requests.models import HardwareRequest
    from apps.hardware_requests.notifications_p2 import revision
    from apps.hardware_requests.notifications_p2_requests import eligible_charge
    from apps.payments.models import Payment
    space = make_space("recon-hardware-charge")
    owner = make_user("recon-hardware-charge-owner", access_status="active")
    request = HardwareRequest.objects.create(makerspace=space, requester=owner, requester_username=owner.username)
    payment = Payment.objects.create(makerspace=space, member=owner, subject_type="loan_deposit",
        subject_id=request.pk, amount="10.00", currency="usd", provider="unclaimed", created_by=owner)
    envelope = SimpleNamespace(makerspace_id=space.pk, source_id=str(payment.pk), audience="staff",
        event="deposit_raised", revision=revision(payment.created_at, payment.subject_type, payment.subject_id),
        context={"request_id": request.pk})
    assert eligible_charge(envelope)
    envelope.context["request_id"] = request.pk + 1
    assert not eligible_charge(envelope)
    envelope.context["request_id"] = request.pk
    envelope.event = "late_fee_raised"
    assert not eligible_charge(envelope)
