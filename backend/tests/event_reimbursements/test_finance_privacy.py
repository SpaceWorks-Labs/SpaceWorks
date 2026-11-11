"""AO19 bank encryption, audited reveal, masked export and RECORD_PAYMENT isolation."""
import json
from uuid import UUID
import pytest
from django.db import connection
from apps.accounts import rbac
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.event_reimbursements import claim_workflow
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts import payee_workflow, exports
from apps.payments.event_payouts.errors import PayoutError
from apps.organizations.models import Organization, OrganizationMembership, OrganizationMakerspace
from tests.accounts.test_reauthentication import request as session_request
from .helpers import submitted, decision_data
from .conftest import cmd, keyed

pytestmark = pytest.mark.django_db(transaction=True)


def test_bank_ciphertext_reveal_and_masked_csv_never_execute_a_transfer(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 10000))
    obligation = EventPayoutObligation.objects.get(source_uuid=claim.uuid)
    details = {"holder_name": "Private Payee Alpha", "account_number": "123456789012", "ifsc": "SBIN0001234", "bank_name": "Private Bank Alpha"}
    data = cmd(obligation.version, expected_payee_version=None, country="IN", method="bank_transfer", template_key="in_bank",
        template_version=1, details=details, disclosure_version=1)
    # Core finance commands bind the Idempotency-Key header to the body's operation_id.
    result = payee_workflow.put(request=keyed(world.member_session, data), obligation_id=obligation.pk, data=data)
    payee_id = UUID(result["payee_revision_id"])
    with connection.cursor() as cursor:
        cursor.execute("SELECT details FROM payments_eventpayeerevision WHERE id=%s", [payee_id])
        raw = cursor.fetchone()[0]
    assert raw.startswith("pii:gcm:v1:")
    assert all(value not in raw for value in details.values())
    obligation.refresh_from_db()
    data = cmd(obligation.version, purpose="verify_routing", reason_code="other", payee_revision_id=payee_id,
        expected_payee_version=result["payee_version"])
    revealed = payee_workflow.reveal(request=keyed(world.finance, data), obligation_id=obligation.pk, data=data)
    assert revealed["details"] == details
    assert AuditLog.objects.filter(makerspace=world.space, action="finance.event_payout.payee_revealed").count() == 1
    obligation.refresh_from_db()
    data = cmd(obligation.version, payee_revision_id=payee_id, expected_payee_version=result["payee_version"])
    payee_workflow.review(request=keyed(world.finance, data), obligation_id=obligation.pk, verified=True, data=data)
    from apps.payments.event_payouts import eligibility_workflow
    obligation.refresh_from_db()
    data = cmd(obligation.version, eligibility_revision=obligation.eligibility_revision, reason_code="verified_attendance")
    eligibility_workflow.acknowledge(request=keyed(world.finance, data), obligation_id=obligation.pk, data=data)
    data = cmd(obligation_ids=[obligation.pk], currency="INR")
    batch = exports.create(request=keyed(world.finance, data), makerspace_id=world.space.pk, data=data)
    csv = exports.download(request=world.finance, makerspace_id=world.space.pk, batch_id=UUID(batch["id"]))
    encoded = csv.decode() if isinstance(csv, bytes) else str(csv)
    audit = json.dumps(list(AuditLog.objects.filter(makerspace=world.space).values("meta")), default=str)
    for value in details.values():
        assert value not in encoded and value not in audit
    assert not obligation.entries.exists()
    world.pool.refresh_from_db()
    assert world.pool.committed_minor == 10000


def test_record_payment_only_organization_delegate_has_no_finance_access(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk,
        data=decision_data(world, claim, line_id, 10000))
    obligation = EventPayoutObligation.objects.get(source_uuid=claim.uuid)
    actor = User.objects.create_user(username="front-desk-only", account_kind="member")
    organization = Organization.objects.create(name="Front desk", slug="front-desk-organization")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=world.space, relationship="manager")
    OrganizationMembership.objects.create(organization=organization, user=actor, granted_actions=["record_payment"])
    assert rbac.can(actor, rbac.Action.RECORD_PAYMENT, world.space.pk)
    assert not rbac.can(actor, rbac.Action.VIEW_FINANCE, world.space.pk)
    req = session_request(actor, surface="delegated")
    with pytest.raises(PayoutError) as exc:
        payee_workflow.reveal(request=req, obligation_id=obligation.pk,
            data=cmd(obligation.version, purpose="verify_routing", reason_code="other"))
    assert exc.value.status_code == 403
    assert not AuditLog.objects.filter(actor=actor, action="finance.event_payout.payee_revealed").exists()
