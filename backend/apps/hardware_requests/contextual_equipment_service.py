"""Transactional contextual request orchestration; entrypoints must validate input."""
import json
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.http import Http404

from apps.accounts.account_obligations import lock_obligation_owner
from apps.accounts.loan_context_identity import borrower_aliases, borrower_survivor
from apps.accounts.models import User
from apps.accounts.staff_identity import is_person, is_platform
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.hardware_requests.request_submission_locked import submit_locked
from apps.hardware_requests.request_workflow import RequesterSnapshot
from apps.inventory.equipment_proposal_receipts import (
    canonical_intent_json, create_receipt, locked_receipt, make_proposal_intent,
    proposal_fingerprint_from_snapshot, receipt_matches,
)
from apps.inventory.models import InventoryProduct
from apps.inventory.equipment_kit_validation import public_safe
from apps.inventory.models_equipment_proposals import (
    EquipmentKitAllocation, EquipmentKitTemplate, EquipmentKitVersion, EquipmentProposalReceipt,
)
from apps.makerspaces.guards import require_feature, require_module, require_module_for_servable, require_module_locked
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.request_access import require_current_term
from apps.hardware_requests.guest_lending import admit_borrower
from apps.presence.guard import require_active_account
from apps.separability import equipment_context_bridge as bridge
from apps.tenant_migration.gate_runtime import assert_write_allowed, boundary_tenant_write

# Re-exported: existing callers import these names from this module.
from .contextual_equipment_common import ProposalConflict, _aliases, _require_same_outcome  # noqa: F401
from .contextual_equipment_execution import _create_pending


def _preflight_equipment(maker, items, kit):
    """Read-only admission before a mandatory key may be provisioned."""
    if kit is None:
        ids = [item["product_id"] for item in items]
        count = InventoryProduct.objects.filter(
            makerspace=maker, pk__in=ids, is_public=True, is_archived=False, is_consumable=False,
        ).count()
        if count != len(ids):
            raise Http404
        require_module(maker, "request_workflow")
        require_feature(maker, "loans.enabled")
        return
    version = EquipmentKitVersion.objects.filter(
        template_id=kit["id"], template__makerspace=maker, template__published_for_contexts=True,
        template__archived=False, version=kit["version"],
    ).first()
    if version is None or not isinstance(version.lines, list):
        raise Http404
    if any(not isinstance(line, dict) or type(line.get("product_id")) is not int
           or not 0 < line["product_id"] <= 9007199254740991 for line in version.lines):
        raise Http404
    ids = [line["product_id"] for line in version.lines]
    products = {p.pk: p for p in InventoryProduct.objects.filter(makerspace=maker, pk__in=ids)}
    from apps.makerspaces.platform import feature_enabled
    if not public_safe(version.lines, products, maker.pk,
                       consumables_enabled=feature_enabled(maker, "inventory.consumables"),
                       returnable_allowed=lambda product: not product.is_consumable):
        raise Http404
    if any(line["kind"] == "returnable" for line in version.lines):
        require_module(maker, "request_workflow")
        require_feature(maker, "loans.enabled")
    else:
        require_feature(maker, "inventory.consumables")


def create_pending(**kwargs):
    """Restart the entire authorization transaction after a unique-key race."""
    maker_id, actor = kwargs["makerspace_id"], kwargs["actor"]
    with boundary_tenant_write(maker_id):
        if not actor or not getattr(actor, "is_authenticated", False) or not actor.pk:
            raise Http404
        try:
            actor.refresh_from_db()
        except User.DoesNotExist:
            raise Http404 from None
        if (not actor.is_active or actor.access_status != "active" or actor.is_tenant_dump_stub
                or actor.deletion_requested_at or actor.must_change_password
                or not (is_person(actor) or (is_platform(actor) and actor.is_superuser))):
            raise Http404
        maker = Makerspace.objects.filter(pk=maker_id).first()
        if maker is None:
            raise Http404
        probe = EquipmentProposalReceipt.objects.filter(
            makerspace_id=maker_id, operation_id=kwargs["operation_id"],
        ).values_list("imported_nonreplayable", "creator_id").first()
        if probe is not None and (probe[0] or probe[1] not in _aliases(actor)):
            raise Http404
        if kwargs["intent_kind"] == "self":
            if kwargs["borrower"] is None or kwargs["borrower"].pk != actor.pk:
                raise Http404
            if not maker.public_site_enabled or not maker.public_inventory_enabled:
                raise Http404
            require_module_for_servable(maker, "public_inventory")
            if module_enabled(maker, "membership"):
                # Planning needs no presence session (decision 223 / queue item 7); issue at the desk does.
                admit_borrower(maker, actor, planning=True)
            else:
                require_active_account(actor, maker)
            bridge.preauthorize_self(maker, actor, kwargs["event_registration_id"], kwargs["booking_token"])
        elif kwargs["intent_kind"] == "staff" and (kwargs["event_registration_id"] or kwargs["booking_id"]):
            proposed = bridge.preauthorize_staff(maker, actor, kwargs["event_registration_id"], kwargs["booking_id"])
            if kwargs["borrower_id"] is not None and kwargs["borrower_id"] not in _aliases(proposed):
                raise Http404
            if module_enabled(maker, "membership"):
                admit_borrower(maker, proposed, planning=True)
            else:
                require_active_account(proposed, maker)
        else:
            raise Http404
        _preflight_equipment(maker, kwargs["items"], kwargs["kit"])
        key = prepare_tenant_key(maker_id, create=probe is None)
        with tenant_key_context(key):
            try:
                try:
                    return _create_pending(**kwargs)
                except IntegrityError as exc:
                    if getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None) != "uniq_equipment_proposal_op":
                        raise
                    return _create_pending(**kwargs)
            except DatabaseError as exc:
                if (getattr(exc.__cause__, "sqlstate", None) or getattr(exc.__cause__, "pgcode", None)) == "55P03":
                    raise ProposalConflict("lock_busy") from exc
                raise
