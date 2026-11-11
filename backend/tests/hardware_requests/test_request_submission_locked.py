"""Pending submission seam: real rows and transaction behavior, no mocked workflow."""
import pytest
from django.db import transaction
from apps.accounts.account_obligations import lock_obligation_owner
from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.request_workflow import RequesterSnapshot, submit_request
from apps.hardware_requests.request_submission_locked import submit_locked
from apps.makerspaces.models import Makerspace
from tests.return_helpers import make_product, make_space, make_user

pytestmark = pytest.mark.django_db(transaction=True)


def arguments(owner, actor):
    return {"requester_principal": owner,
            "contact_snapshot": RequesterSnapshot(username=owner.username, name="Borrower", email=owner.email, phone=""),
            "audit_actor": actor, "account_less_marker": "", "contact_key": "",
            "pickup_from": None, "pickup_until": None, "waitlist_entry_id": None}


def test_public_wrapper_keeps_pending_quantity_and_actual_audit_actor():
    space, owner, actor = make_space("seam-wrapper"), make_user("seam-owner"), make_user("seam-actor")
    product = make_product(space)
    before = (product.available_quantity, product.reserved_quantity, product.issued_quantity)
    result = submit_request(space, [{"product": product, "quantity": 2}], "Workshop", **arguments(owner, actor))
    assert result.status == HardwareRequest.Status.PENDING_APPROVAL and result.requester_id == owner.pk
    assert list(result.items.values_list("product_id", "requested_quantity")) == [(product.pk, 2)]
    assert AuditLog.objects.filter(action="request.submitted", target_id=str(result.pk), actor=actor).exists()
    product.refresh_from_db()
    assert (product.available_quantity, product.reserved_quantity, product.issued_quantity) == before


def test_locked_seam_requires_atomic_and_rolls_back_request_and_audit():
    space, owner, actor = make_space("seam-rollback"), make_user("seam-rollback-owner"), make_user("seam-rollback-actor")
    product = make_product(space)
    args = arguments(owner, actor)
    with pytest.raises(RuntimeError, match="atomic"):
        submit_locked(space, [{"product": product, "quantity": 1}], "", **args)
    with pytest.raises(ValueError, match="abort"):
        with transaction.atomic():
            locked_space = Makerspace.objects.select_for_update().get(pk=space.pk)
            args["requester_principal"] = lock_obligation_owner(owner)
            result = submit_locked(locked_space, [{"product": product, "quantity": 1}], "", **args)
            request_id = result.pk
            assert AuditLog.objects.filter(action="request.submitted", target_id=str(request_id)).exists()
            raise ValueError("abort")
    assert not HardwareRequest.objects.filter(pk=request_id).exists()
    assert not AuditLog.objects.filter(action="request.submitted", target_id=str(request_id)).exists()
