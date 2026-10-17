"""Inventory threshold and one-shot watch envelope sources."""
from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import content, fanout, revision
from apps.integrations.destinations import NotificationScope
from apps.integrations.email_templates import render
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.hardware_requests.notifications_p2 import safe_adapter
from apps.makerspaces.platform import feature_enabled
from apps.presence.guard import require_active_member, MemberPresenceRequired, WaiverAcceptanceRequired
from .models import InventoryProduct
from .models_watch import InventoryWatch

STOCK = "inventory.threshold"
WATCH = "inventory.watch"


def public_availability(product):
    return (product.is_public and not product.is_archived
            and product.public_availability_mode != "hidden")


def eligible_stock(envelope):
    row = rbac.scope_notification_policy(InventoryProduct.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id).first()
    return bool(row and not row.is_archived and row.reorder_point > 0
                and row.available_quantity <= row.reorder_point
                and revision(row.updated_at, row.available_quantity, row.reorder_point) == envelope.revision)


@safe_adapter
def notify_stock(product):
    context = {"makerspace": bag(name=product.makerspace.name), "event_name": "low_stock",
               "subject": bag(id=product.pk, name=product.name[:160],
                              available=product.available_quantity, reorder_point=product.reorder_point)}
    rendered = render(product.makerspace, "stock", "staff", "low_stock", context)
    return fanout(space=product.makerspace, feature="stock", stream="stock", event="low_stock",
        kind=STOCK, source=product.pk, subject=product,
        version=revision(product.updated_at, product.available_quantity, product.reorder_point),
        staff=content(rendered), scope=NotificationScope(category=product.category_id),
        context={"product_id": product.pk})


def eligible_watch(envelope):
    row = rbac.scope_notification_policy(InventoryWatch.objects.all(),
        makerspace_id=envelope.makerspace_id).select_related("user", "product").filter(
        pk=envelope.source_id, user_id=envelope.recipient_id).first()
    if row is None or row.ready_at is None or row.notified_at is None:
        return False
    if revision(row.created_at, row.ready_at) != envelope.revision:
        return False
    if not public_availability(row.product) or row.product.available_quantity <= 0:
        return False
    if not envelope.makerspace.public_inventory_enabled or not feature_enabled(envelope.makerspace, "inventory.notify_when_back"):
        return False
    try:
        return require_active_member(row.user, envelope.makerspace).membership.receives_notifications
    except (MemberPresenceRequired, WaiverAcceptanceRequired):
        return False


@safe_adapter
def notify_watch(row, message):
    return fanout(space=row.makerspace, feature="hardware_requests", stream="hardware",
        event="back_available", kind=WATCH, source=row.pk, subject=row,
        version=revision(row.created_at, row.ready_at), owner=row.user,
        own={"subject": message.title, "text": message.body,
             "link": f"/m/{row.makerspace.slug}/items/{row.product_id}"},
        context={"product_id": row.product_id})


def register():
    register_source(STOCK, NotificationSource(eligible_stock))
    register_source(WATCH, NotificationSource(eligible_watch))
