"""Categories, QR boxes, products, QR-tracked assets and a reorder draft.

Each write mirrors the staff console path that owns it: the admin serializers create
categories and products, the QR view's shape creates a box and its label, stock
arrives through `availability.adjust_quantities` (an audited intake), and unit labels
come from `generate_assets_with_qr`. No quantity bucket is written here directly.
"""
from types import SimpleNamespace

from django.db import transaction

from apps.admin_api.serializers_inventory import CategoryAdminSerializer
from apps.admin_api.serializers_inventory_products import InventoryProductAdminCreateSerializer
from apps.audit import services as audit
from apps.boxes.models import Box, QrCode
from apps.inventory import availability
from apps.operations.services_qr_assets import generate_assets_with_qr
from apps.procurement.services_drafts import create_reorder_draft

from . import _showcase_data as data


def seed_inventory(makerspace, manager, inventory_manager):
    categories = {name: _category(makerspace, inventory_manager, name, icon, order)
                  for order, (name, icon) in enumerate(data.CATEGORIES)}
    boxes = [_box(makerspace, inventory_manager, label, location) for label, location in data.BOXES]
    products = {}
    for name, category, box, quantity, mode, public, point, reorder in data.COUNTED_PRODUCTS:
        product = _product(makerspace, inventory_manager, {
            "name": name, "category": categories[category].pk, "box": boxes[box].pk,
            "tracking_mode": "quantity", "public_availability_mode": mode,
            "show_public_count": mode == data.EXACT, "is_public": public,
            "public_self_checkout_enabled": public and mode == data.EXACT,
            "reorder_point": point, "reorder_quantity": reorder,
            "storage_location": data.BOXES[box][1],
            "description": f"{name} from the Tinkerspace tool library.",
        })
        products[name] = availability.adjust_quantities(
            product, delta_available=quantity, delta_damaged=0, delta_lost=0,
            reason="Initial stock", actor=inventory_manager,
        )
    asset_payloads = {}
    for name, category, box, units, mode, public in data.TRACKED_PRODUCTS:
        product = _product(makerspace, inventory_manager, {
            "name": name, "category": categories[category].pk, "box": boxes[box].pk,
            "tracking_mode": "individual", "public_availability_mode": mode,
            "show_public_count": mode == data.EXACT, "is_public": public,
            "storage_location": data.BOXES[box][1],
            "description": f"Serial-tracked {name.lower()}; scan its unit label at handover.",
        })
        serials = [f"TS-{product.pk:03d}-{index:02d}" for index in range(1, units + 1)]
        created, _batch = generate_assets_with_qr(inventory_manager, product, {
            "count": units, "serial_numbers": serials, "create_print_batch": True,
            "name_prefix": name,
        })
        product.refresh_from_db()
        products[name] = product
        asset_payloads[name] = [row["qr"].payload for row in created]
    # The PETG spool sits below its reorder point, so the reorder list shows it and a
    # procurement draft is raised for it through the same service the console uses.
    create_reorder_draft(manager, makerspace, products["PETG Filament 1 kg"].pk)
    return SimpleNamespace(boxes=boxes, products=products, asset_payloads=asset_payloads)


def _context(actor, **extra):
    return {"request": SimpleNamespace(user=actor), **extra}


def _category(makerspace, actor, name, icon, order):
    serializer = CategoryAdminSerializer(
        data={"name": name, "icon": icon, "display_order": order},
        context=_context(actor, makerspace_id=makerspace.pk),
    )
    serializer.is_valid(raise_exception=True)
    category = serializer.save(makerspace_id=makerspace.pk)
    audit.record(actor, "category.created", makerspace=makerspace, target=category)
    return category


def _box(makerspace, actor, label, location):
    with transaction.atomic():
        box = Box.objects.create(makerspace=makerspace, label=label, location=location,
                                 description=f"{label}, labelled with its QR code.")
        QrCode.objects.create(makerspace=makerspace, payload=box.code,
                              target_type=QrCode.TargetType.BOX, target_id=box.id, created_by=actor)
        audit.record(actor, "qr.box_created", makerspace=makerspace, target=box)
    return box


def _product(makerspace, actor, values):
    serializer = InventoryProductAdminCreateSerializer(data=values, context=_context(actor))
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        product = serializer.save(makerspace_id=makerspace.pk)
        audit.record(actor, "inventory.created", makerspace=makerspace, target=product)
    return product
