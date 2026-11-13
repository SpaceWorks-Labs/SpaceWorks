"""Create an advisory consumable plan without touching inventory quantity."""
from django.core.exceptions import ValidationError
from django.db import connection

from apps.audit import services as audit
from apps.inventory.equipment_kit_validation import normalize_lines
from apps.inventory.models import InventoryProduct
from apps.inventory.models_equipment_proposals import (
    EquipmentConsumablePlan, EquipmentKitTemplate, EquipmentKitVersion,
)
from apps.makerspaces.guards import require_feature
from django.utils.translation import gettext


def create_plan_locked(*, makerspace, borrower, actor, kit_id, version_number):
    """Caller holds tenant and borrower locks, source gates, and domain authority."""
    if not connection.in_atomic_block:
        raise RuntimeError("Plan creation requires an atomic transaction")
    require_feature(makerspace, "inventory.consumables")
    template = EquipmentKitTemplate.objects.select_for_update(nowait=True, of=("self",)).filter(
        pk=kit_id, makerspace=makerspace, archived=False, published_for_contexts=True,
    ).first()
    if template is None:
        raise ValidationError(gettext("Kit is unavailable."))
    version = EquipmentKitVersion.objects.select_for_update(nowait=True, of=("self",)).filter(
        template=template, version=version_number,
    ).first()
    if version is None:
        raise ValidationError(gettext("Kit is unavailable."))
    if not isinstance(version.lines, list) or any(
        not isinstance(line, dict) or type(line.get("product_id")) is not int
        or not 0 < line["product_id"] <= 9007199254740991 for line in version.lines
    ):
        raise ValidationError(gettext("Kit is unavailable."))
    ids = [line["product_id"] for line in version.lines]
    products = {p.pk: p for p in InventoryProduct.objects.select_for_update(nowait=True, of=("self",))
                .filter(pk__in=ids, makerspace=makerspace).order_by("pk")}
    lines = normalize_lines(version.lines, products, makerspace.pk)
    if any(line["kind"] != "consumable" or not products[line["product_id"]].is_public for line in lines):
        raise ValidationError(gettext("Kit is unavailable."))
    plan = EquipmentConsumablePlan.objects.create(
        makerspace=makerspace, borrower=borrower, kit_version=version, lines=lines,
    )
    audit.record(actor, "inventory.equipment_consumable_plan_created", makerspace=makerspace, target=plan)
    return plan
