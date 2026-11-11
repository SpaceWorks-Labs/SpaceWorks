"""Durable initialization identity and same-transaction canonical request binding."""
from uuid import uuid4
import pytest
from django.db import transaction
from apps.event_reimbursements import programme_workflow, request_workflow
from apps.event_reimbursements.models import GrantRequest, ReimbursementProgramme
from apps.event_reimbursements.request_form_adapter import prepare
from apps.events.models import EventRegistration, EventCommandReceipt
from apps.events.services_registration import register
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.events.programme_locks import fences
from apps.events.contracts.providers import LockedContext
from apps.payments.event_payouts.errors import PayoutError
from .helpers import block, requested
from .conftest import cmd

pytestmark = pytest.mark.django_db(transaction=True)


def test_initialization_same_policy_after_configure_and_receipt_expiry_never_funds_again(world):
    value = cmd(currency="INR", initial_total_minor=1000000, initial_settings={})
    result = programme_workflow.create_or_get(request=world.finance, event_id=world.event.pk, data=value)
    assert result["created"] is False
    assert world.pool.entries.filter(kind="fund", reason_code="initial_funding").count() == 1
    assert ReimbursementProgramme.objects.filter(event=world.event).count() == 1
    changed = {**value, "initial_total_minor": 999999}
    with pytest.raises(PayoutError) as exc:
        programme_workflow.create_or_get(request=world.finance, event_id=world.event.pk, data=changed)
    assert exc.value.detail["code"] == "idempotency_conflict"


def test_outer_late_failure_rolls_back_registration_and_support_request(world):
    operation = uuid4()
    prepared = prepare(programme=world.programme, event=world.event, actor=world.owner, operation_id=operation, block=block(world))
    key = prepare_tenant_key(world.space.pk)
    with pytest.raises(RuntimeError), tenant_key_context(key), transaction.atomic(), fences(
        tenant_ids=(world.space.pk,), account_ids=(world.owner.pk,),
    ):
        registration = register(world.event, member=world.owner, actor=world.owner)
        request_workflow.submit_application_locked(event=world.event, actor=world.owner, prepared=prepared,
            registration=registration, locks=LockedContext(event_id=world.event.pk,
                tenant_ids=(world.space.pk,), account_ids=(world.owner.pk,)))
        raise RuntimeError("injected failure before outer receipt")
    assert not GrantRequest.objects.filter(event=world.event).exists()
    assert not EventRegistration.objects.filter(event=world.event).exists()
    assert not EventCommandReceipt.objects.filter(operation_uuid=operation).exists()


def test_intake_replay_returns_same_request_and_changed_payload_conflicts(world):
    from .helpers import participate
    participate(world)
    value = cmd(reimbursement_request=block(world))
    first = request_workflow.submit(event_id=world.event.pk, actor=world.owner, request=world.member_session, data=value)
    assert request_workflow.submit(event_id=world.event.pk, actor=world.owner, request=world.member_session, data=value) == first
    changed = {**value, "reimbursement_request": {**value["reimbursement_request"], "need_statement": "Different"}}
    with pytest.raises(PayoutError) as exc:
        request_workflow.submit(event_id=world.event.pk, actor=world.owner, request=world.member_session, data=changed)
    assert exc.value.detail["code"] == "idempotency_conflict"
    assert GrantRequest.objects.filter(event=world.event).count() == 1
