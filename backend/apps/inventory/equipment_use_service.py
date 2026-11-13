"""Idempotent linked use, delegating all quantity changes to availability."""
import hmac
import json

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.http import Http404

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.loan_context_identity import borrower_aliases
from apps.admin_api.permissions import require_action
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.hardware_requests.loan_context_access import authorized_request_queryset
from apps.inventory.availability_quantities import consume_available_with_adjustment
from apps.inventory.equipment_use_intent_v2 import canonical_use_intent_json, make_use_intent, use_fingerprint_from_snapshot
from apps.inventory.models import InventoryProduct
from apps.inventory.models_equipment_proposals import (
    EquipmentConsumablePlan, EquipmentConsumableUseReceipt, EquipmentKitAllocation,
)
from apps.makerspaces.folded_capabilities import require_capability
from apps.makerspaces.guards import require_module, require_module_locked
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import assert_write_allowed, boundary_tenant_write


class UseConflict(Exception):
    pass


def _preflight_source(actor, maker, kind, source_id, product_id):
    if kind not in {"allocation", "plan"}:
        raise Http404
    product = rbac.scope_by_action(
        actor, rbac.Action.EDIT_INVENTORY,
        InventoryProduct.objects.filter(makerspace=maker, is_consumable=True, is_archived=False),
    ).filter(pk=product_id).first()
    model = EquipmentKitAllocation if kind == "allocation" else EquipmentConsumablePlan
    source = model.objects.filter(pk=source_id, makerspace=maker).first()
    if product is None or source is None:
        raise Http404
    if kind == "allocation" and not authorized_request_queryset(actor, maker).filter(pk=source.request_id).exists():
        raise Http404
    if not isinstance(source.lines, list) or not any(
        isinstance(line, dict) and line.get("product_id") == product_id and line.get("kind") == "consumable"
        for line in source.lines
    ):
        raise Http404


def _source(actor, maker, kind, pk, product_id):
    model = EquipmentKitAllocation if kind == "allocation" else EquipmentConsumablePlan
    row = model.objects.select_for_update(nowait=True, of=("self",)).filter(
        pk=pk, makerspace=maker,
    ).first()
    if row is None:
        raise Http404
    if kind == "allocation" and not authorized_request_queryset(actor, maker).filter(pk=row.request_id).exists():
        raise Http404
    if not isinstance(row.lines, list) or not any(
        isinstance(line, dict) and line.get("product_id") == product_id and line.get("kind") == "consumable"
        for line in row.lines
    ):
        raise Http404
    return row


def linked_use(**kwargs):
    maker_id, actor = kwargs["makerspace_id"], kwargs["actor"]
    with boundary_tenant_write(maker_id):
        maker = Makerspace.objects.filter(pk=maker_id).first()
        if maker is None or not actor or not getattr(actor, "is_authenticated", False):
            raise Http404
        try:
            actor.refresh_from_db()
        except User.DoesNotExist:
            raise Http404 from None
        require_module(maker, "staff_admin")
        require_capability(maker, "inventory.consumables")
        require_action(actor, rbac.Action.EDIT_INVENTORY, maker.pk)
        probe = EquipmentConsumableUseReceipt.objects.filter(
            makerspace_id=maker_id, operation_id=kwargs["operation_id"],
        ).values_list("imported_nonreplayable", "creator_id").first()
        try:
            aliases = borrower_aliases(actor)
        except (ValueError, RuntimeError, User.DoesNotExist):
            raise Http404 from None
        if probe is not None and (probe[0] or probe[1] not in aliases):
            raise Http404
        _preflight_source(actor, maker, kwargs["source_kind"], kwargs["source_id"], kwargs["product_id"])
        key = prepare_tenant_key(maker_id, create=probe is None)
        with tenant_key_context(key):
            try:
                try:
                    return _linked_use(**kwargs)
                except IntegrityError as exc:
                    if getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None) != "uniq_equipment_use_op":
                        raise
                    return _linked_use(**kwargs)
            except DatabaseError as exc:
                if (getattr(exc.__cause__, "sqlstate", None) or getattr(exc.__cause__, "pgcode", None)) == "55P03":
                    raise UseConflict("lock_busy") from exc
                raise


@transaction.atomic
def _linked_use(*, actor, makerspace_id, product_id, operation_id, source_kind, source_id, quantity, note):
    if source_kind not in {"allocation", "plan"}:
        raise Http404
    assert_write_allowed(makerspace_id)
    assert_mapped_write_allowed(makerspace_id)
    maker = Makerspace.objects.select_for_update(nowait=True, no_key=True, of=("self",)).get(pk=makerspace_id)
    try:
        actor.refresh_from_db()
    except User.DoesNotExist:
        raise Http404 from None
    require_module_locked(maker, "staff_admin")
    require_capability(maker, "inventory.consumables")
    require_action(actor, rbac.Action.EDIT_INVENTORY, maker.pk)
    receipt = EquipmentConsumableUseReceipt.objects.select_for_update(nowait=True, of=("self",)).filter(
        makerspace=maker, operation_id=operation_id,
    ).first()
    if receipt is not None and receipt.imported_nonreplayable:
        raise Http404
    old = None
    if receipt is not None:
        try:
            old = json.loads(receipt.intent_snapshot)
            canonical_use_intent_json(old)
            source_matches = (
                old["source_kind"] == "allocation" and receipt.allocation_id == old["source_id"] and receipt.plan_id is None
                or old["source_kind"] == "plan" and receipt.plan_id == old["source_id"] and receipt.allocation_id is None
            )
            if (receipt.intent_version != 2 or old["makerspace_id"] != maker.pk or old["operation_id"] != str(operation_id)
                    or old["original_creator_id"] != receipt.creator_id
                    or old["product_id"] != receipt.product_id or not source_matches
                    or receipt.adjustment.makerspace_id != maker.pk or receipt.adjustment.product_id != receipt.product_id
                    or receipt.adjustment.delta_available != -receipt.quantity
                    or not hmac.compare_digest(receipt.payload_sha256, use_fingerprint_from_snapshot(old))):
                raise ValueError
        except (TypeError, ValueError, ValidationError):
            raise Http404 from None
        try:
            actor_aliases = borrower_aliases(actor)
        except (ValueError, RuntimeError):
            raise Http404 from None
        if receipt.creator_id not in actor_aliases:
            raise Http404
    # Lock both old and proposed product/source rows in deterministic order.
    product_ids = sorted({product_id, *([old["product_id"]] if old else [])})
    products = {p.pk: p for p in InventoryProduct.objects.select_for_update(nowait=True, of=("self",)).filter(
        makerspace=maker, pk__in=product_ids, is_consumable=True, is_archived=False,
    ).order_by("pk")}
    if len(products) != len(product_ids):
        raise Http404
    sources = {(source_kind, source_id, product_id)}
    if old:
        sources.add((old["source_kind"], old["source_id"], old["product_id"]))
    locked = {(kind, pk, product): _source(actor, maker, kind, pk, product)
              for kind, pk, product in sorted(sources)}
    source = locked[(source_kind, source_id, product_id)]
    intent = make_use_intent(
        makerspace_id=maker.pk, operation_id=operation_id,
        original_creator_id=receipt.creator_id if receipt else actor.pk, product_id=product_id,
        source_kind=source_kind, source_id=source_id, quantity=quantity, note=note,
    )
    digest = use_fingerprint_from_snapshot(intent)
    if receipt is not None:
        if not hmac.compare_digest(receipt.payload_sha256, digest):
            raise UseConflict("operation_conflict")
        return products[product_id], receipt.adjustment, True
    product, adjustment = consume_available_with_adjustment(
        products[product_id], quantity, reason=f"Consumable used{': ' + note if note else ''}", actor=actor,
    )
    EquipmentConsumableUseReceipt.objects.create(
        makerspace=maker, operation_id=operation_id, creator=actor, product=product, quantity=quantity,
        payload_sha256=digest, intent_snapshot=canonical_use_intent_json(intent), intent_version=2,
        allocation=source if source_kind == "allocation" else None,
        plan=source if source_kind == "plan" else None, adjustment=adjustment,
    )
    return product, adjustment, False
