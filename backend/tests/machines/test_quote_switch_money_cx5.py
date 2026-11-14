"""Machine-service quote boundaries and ledger interconnections through the real routes."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.machines import role_scope, service_workflow_review as review
from apps.machines.models import MachineServiceRequest
from apps.machines.service_workflow import complete, start
from apps.payments.models import Payment
from tests.machines.test_quote_routes_mod2 import _approve, _client, _decline, _quoted
from tests.refusal_helpers_mod2b import refused

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("action", ["approve", "decline"])
def test_machine_service_off_refuses_quote_answer_and_on_restores_the_same_job(action):
    w, member, row = _quoted("cx5-quote-module")
    original = list(w.space.enabled_modules)
    w.space.enabled_modules = [key for key in original if key != "machine_service"]
    w.space.save(update_fields=["enabled_modules"])
    api = _client(member)
    def answer():
        return _approve(api, row, row.quote_digest) if action == "approve" else _decline(api, row)
    refused(answer(), 404, "module_disabled")
    row.refresh_from_db()
    assert row.status == "quoted" and row.quote_approved_at is None
    assert not Payment.objects.filter(subject_type="machine_service_request", subject_id=row.pk).exists()
    assert not AuditLog.objects.filter(action="machine_service.quote_approved", target_id=str(row.pk)).exists()
    w.space.enabled_modules = original
    w.space.save(update_fields=["enabled_modules"])
    restored = answer()
    assert restored.status_code == 200, restored.content
    row.refresh_from_db()
    assert row.status == ("accepted" if action == "approve" else "cancelled")


def test_quote_expiry_is_exclusive_at_the_exact_deadline(monkeypatch):
    w, member, row = _quoted("cx5-quote-deadline")
    deadline = row.quote_expires_at
    monkeypatch.setattr(review.timezone, "now", lambda: deadline)
    refused(_approve(_client(member), row, row.quote_digest), 409, "service_invalid_transition")
    row.refresh_from_db()
    assert row.status == "quoted" and row.quote_approved_at is None
    assert not Payment.objects.filter(subject_type="machine_service_request", subject_id=row.pk).exists()
    assert not AuditLog.objects.filter(action="machine_service.quote_approved", target_id=str(row.pk)).exists()


@pytest.mark.parametrize("actual,expected", [(20, "45.00"), (300, "65.00")])
def test_completion_without_online_rail_records_one_unclaimed_charge_capped_at_the_quote(actual, expected):
    w, member, row = _quoted("cx5-quote-ledger")
    w.space.enabled_modules = [key for key in w.space.enabled_modules if key != "payments"]
    w.space.save(update_fields=["enabled_modules"])
    assert _approve(_client(member), row, row.quote_digest).status_code == 200
    row.refresh_from_db()
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    complete(row, w.staff, actual_minutes=actual, consumptions=[])
    payment = Payment.objects.get(subject_type="machine_service_request", subject_id=row.pk)
    assert payment.provider == "unclaimed" and payment.status == "pending"
    assert payment.amount == Decimal(expected)
    assert payment.pricing_snapshot and payment.member_id == member.pk
    url = reverse("admin-machine-service-request-complete", args=[row.pk])
    response = _client(w.staff).post(url, {"actual_minutes": actual, "consumptions": []}, format="json")
    refused(response, 409, "service_invalid_transition")
    assert Payment.objects.filter(subject_type="machine_service_request", subject_id=row.pk).count() == 1
    assert AuditLog.objects.filter(action="machine_service.completed", target_id=str(row.pk)).count() == 1


@pytest.mark.parametrize("key", ["charges.enabled", "charges.machines"])
def test_approved_prepay_quote_queues_free_if_charges_are_switched_off(key):
    w, member, row = _quoted("cx5-quote-free")
    MachineServiceRequest.objects.filter(pk=row.pk).update(prepay=True)
    w.space.enabled_features = [feature for feature in w.space.enabled_features if feature != key]
    w.space.save(update_fields=["enabled_features"])
    response = _approve(_client(member), row, row.quote_digest)
    assert response.status_code == 200, response.content
    row.refresh_from_db()
    assert row.status == "accepted" and row.quote_approved_at is not None
    assert not Payment.objects.filter(subject_type="machine_service_request", subject_id=row.pk).exists()
    assert AuditLog.objects.filter(action="machine_service.quote_approved", target_id=str(row.pk)).count() == 1
