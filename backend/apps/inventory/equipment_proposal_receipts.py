"""Receipt storage; caller must freshly authorize the actor, borrower and sources."""
import hmac
from django.core.exceptions import ValidationError
from django.db import connection
from apps.inventory.equipment_intent_v2 import (
    canonical_intent_json, make_proposal_intent, proposal_fingerprint_from_snapshot,
)
from apps.inventory.models_equipment_proposals import EquipmentProposalReceipt
from django.utils.translation import gettext

FINGERPRINT_VERSION = 2


def receipt_matches(receipt, expected_digest):
    return (not receipt.imported_nonreplayable and receipt.intent_version == FINGERPRINT_VERSION
            and receipt.fingerprint_version == FINGERPRINT_VERSION and isinstance(receipt.payload_sha256, str)
            and isinstance(expected_digest, str) and hmac.compare_digest(receipt.payload_sha256, expected_digest))


def locked_receipt(*, makerspace_id, operation_id):
    if not connection.in_atomic_block:
        raise RuntimeError("Proposal receipt lookup requires an atomic transaction")
    return EquipmentProposalReceipt.objects.select_for_update(of=("self",), nowait=True).filter(
        makerspace_id=makerspace_id, operation_id=operation_id).first()


def create_receipt(*, makerspace_id, operation_id, borrower, creator, snapshot, request=None, plan=None):
    if not connection.in_atomic_block:
        raise RuntimeError("Proposal receipt creation requires an atomic transaction")
    if (request is None) == (plan is None):
        raise ValidationError(gettext("Invalid proposal."))
    kind = "request" if request is not None else "consumable_plan"
    if (creator is None or snapshot.get("original_creator_id") != creator.pk
            or snapshot.get("makerspace_id") != makerspace_id or snapshot.get("original_borrower_id") != borrower.pk
            or snapshot.get("operation_id") != str(operation_id) or snapshot.get("outcome_kind") != kind):
        raise ValidationError(gettext("Invalid proposal."))
    return EquipmentProposalReceipt.objects.create(
        makerspace_id=makerspace_id, operation_id=operation_id, borrower=borrower, creator=creator,
        fingerprint_version=FINGERPRINT_VERSION, payload_sha256=proposal_fingerprint_from_snapshot(snapshot),
        intent_version=FINGERPRINT_VERSION, intent_snapshot=canonical_intent_json(snapshot), outcome_kind=kind,
        request=request, consumable_plan=plan,
    )
