"""Trusted hashes, generations, totals and explicit multi-person allocations."""
import json
from types import SimpleNamespace
from uuid import UUID
import pytest
from apps.accounts.models import User
from apps.event_reimbursements import claim_workflow
from apps.event_reimbursements.models import ReimbursementClaim
from apps.payments.event_payouts.errors import PayoutError
from apps.payments.event_payouts.receipt_models import ReceiptUse
from .helpers import accepted, submitted, decision_data
from .conftest import cmd

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("change", [{"sha256": "b" * 64}, {"generation": 2}, {"receipt_total_minor": 9999}])
def test_tampered_or_overallocated_receipt_refuses_without_new_revision(world, monkeypatch, change):
    claim, _, line_id = submitted(world, monkeypatch)
    value = decision_data(world, claim, line_id, 0, outcome="returned_for_info")
    from django.utils import timezone
    from datetime import timedelta
    value.update(line_decisions=[], info_due_at=timezone.now() + timedelta(days=3))
    claim_workflow.decide(request=world.finance, event_id=world.event.pk, claim_id=claim.pk, data=value)
    claim.refresh_from_db()
    draft = json.loads(claim.draft_payload)
    draft["lines"][0]["receipt"].update(change)
    claim_workflow.save_draft(event_id=world.event.pk, actor=world.owner, request=world.member_session,
        data=cmd(claim.version, lines=draft["lines"]))
    claim.refresh_from_db()
    with pytest.raises(PayoutError):
        claim_workflow.submit(event_id=world.event.pk, actor=world.owner, request=world.member_session,
            data=cmd(claim.version, current_revision=claim.current_revision_id))
    claim.refresh_from_db()
    assert claim.state == "returned_for_info" and claim.revisions.count() == 1


def test_cross_claim_duplicate_requires_bounded_finance_allocation_override(world, monkeypatch):
    first_award = accepted(world, amount=5000)
    other = User.objects.create_user(username="shared-receipt-owner", account_kind="member", email="other@example.test",
        phone="+919988776655")
    second = SimpleNamespace(**{**world.__dict__, "owner": other})
    from tests.accounts.test_reauthentication import request as session_request
    second.member_session = session_request(other, surface="member")
    second_award = accepted(second, amount=5000)
    first, asset, first_line = submitted(world, monkeypatch, amount=5000, award=first_award, receipt_total=10000)
    with pytest.raises(PayoutError) as exc:
        submitted(second, monkeypatch, amount=5000, award=second_award, receipt_total=10000)
    assert exc.value.detail["code"] == "receipt_duplicate"
    second_claim = ReimbursementClaim.objects.get(award=second_award)
    second_line = UUID(json.loads(second_claim.draft_payload)["lines"][0]["line_uuid"])
    use = ReceiptUse.objects.get(makerspace=world.space, sha256=asset.sha256)
    value = cmd(first.version, asset_id=asset.pk, expected_receipt_use_version=use.version,
        receipt_total_minor=10000, original_currency="INR", allocations=[
            {"claim_uuid": first.uuid, "line_uuid": first_line, "original_amount_minor": 5000},
            {"claim_uuid": second_claim.uuid, "line_uuid": second_line, "original_amount_minor": 5000}],
        reason_code="receipt_shared", note="Two travellers share this receipt")
    claim_workflow.receipt_override(request=world.finance, event_id=world.event.pk, claim_id=first.pk, data=value)
    claim_workflow.submit(event_id=world.event.pk, actor=other, request=second.member_session,
        data=cmd(second_claim.version, current_revision=None))
    use.refresh_from_db()
    assert use.allocations.filter(use_version=use.version).count() == 2
    assert sum(use.allocations.filter(use_version=use.version).values_list("amount_minor", flat=True)) == 10000


def test_receipt_owner_metadata_contains_no_object_locator_or_byte_url(world, monkeypatch):
    claim, asset, _ = submitted(world, monkeypatch)
    from apps.event_reimbursements.receipt_uploads import metadata, owned_asset
    value = metadata(owned_asset(event=world.event, owner_id=world.owner.pk, asset_id=asset.pk))
    assert not {"object_key", "staging_key", "url", "download", "original_filename"} & value.keys()
    with pytest.raises(PayoutError) as exc:
        owned_asset(event=world.event, owner_id=world.manager.pk, asset_id=asset.pk)
    assert exc.value.status_code == 404
