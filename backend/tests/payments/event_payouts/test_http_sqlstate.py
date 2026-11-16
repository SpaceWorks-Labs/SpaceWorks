"""Real payout unique violations map to safe typed HTTP refusals on psycopg2."""
import psycopg2
import pytest
from django.db import IntegrityError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.payments.event_payouts import payout_workflow
from apps.payments.event_payouts.payout_models import EventPayoutEntry
from apps.payments.event_payouts.queries import paid
from tests.accounts.reauth_helpers import force_recent_authenticate
from .conftest import request_for
from .test_ledger import ready_payee, record_data

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize(("collision_field", "code"), [
    ("operation_id", "idempotency_conflict"), ("id", "finance_conflict"),
])
def test_psycopg2_duplicate_payout_returns_409_without_partial_writes(finance_bundle, monkeypatch,
                                                                    collision_field, code):
    b = finance_bundle
    payee = ready_payee(b)
    first = record_data(b.obligation, payee, 10000)
    saved = payout_workflow.record(request=request_for(b.actor, first), obligation_id=b.obligation.pk, data=first)
    entry = EventPayoutEntry.objects.get(pk=saved["entry_id"])
    second = record_data(b.obligation, payee, 10000)
    before_version = b.obligation.version
    before_audit = AuditLog.objects.filter(makerspace=b.space, action="finance.event_payout.recorded").count()
    create = EventPayoutEntry.objects.create
    failures = []

    def collide(**kwargs):
        # Inject only a duplicate value; PostgreSQL, not a fabricated exception,
        # enforces the actual payout constraint after all workflow admission.
        kwargs[collision_field] = getattr(entry, collision_field)
        try:
            return create(**kwargs)
        except IntegrityError as exc:
            failures.append(exc)
            raise

    client = APIClient()
    force_recent_authenticate(client, b.actor)
    path = reverse("finance-event-payout-record", kwargs={
        "makerspace_id": b.space.pk, "obligation_id": b.obligation.pk,
    })
    with monkeypatch.context() as patch:
        patch.setattr(EventPayoutEntry.objects, "create", collide)
        response = client.post(path, second, format="json", HTTP_IDEMPOTENCY_KEY=str(second["operation_id"]),
                               HTTP_ORIGIN="http://localhost:5000")
    assert response.status_code == 409, response.data
    assert response.data["code"] == code
    assert len(failures) == 1
    driver = failures[0].__cause__
    assert isinstance(driver, psycopg2.errors.UniqueViolation)
    assert driver.pgcode == "23505"
    assert ("operation_id" in driver.diag.constraint_name) is (collision_field == "operation_id")
    assert str(entry.operation_id) not in response.content.decode()
    assert driver.diag.constraint_name not in response.content.decode()
    assert response["Cache-Control"] == "private, no-store"
    b.obligation.refresh_from_db()
    assert b.obligation.version == before_version
    assert paid(b.obligation) == 10000
    assert b.obligation.entries.count() == 1
    assert b.obligation.command_receipts.filter(operation_id=second["operation_id"]).count() == 0
    assert AuditLog.objects.filter(makerspace=b.space, action="finance.event_payout.recorded").count() == before_audit

    response = client.post(path, second, format="json", HTTP_IDEMPOTENCY_KEY=str(second["operation_id"]),
                           HTTP_ORIGIN="http://localhost:5000")
    assert response.status_code == 200, response.data
    assert response.data["id"] == str(b.obligation.pk)
    assert paid(b.obligation) == 20000
    assert b.obligation.entries.count() == 2
