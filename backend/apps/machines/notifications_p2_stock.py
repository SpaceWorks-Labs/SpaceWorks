"""Consumable/procurement notification adapter with source and type authority."""
from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import content, fanout, revision
from apps.integrations.destinations import NotificationScope
from apps.integrations.email_templates import render
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.hardware_requests.notifications_p2 import safe_adapter
from .notifications_p2_certifications import staff_allowed

KIND = "machines.procurement"


def version(item):
    return revision(item.updated_at, item.status, item.machine_type_id)


def eligible(envelope):
    from apps.procurement.models import ToBuyItem
    item = rbac.scope_notification_policy(ToBuyItem.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id).first()
    if item is None or version(item) != envelope.revision or envelope.audience != "staff":
        return False
    if item.machine_type_id and not staff_allowed(envelope, item.machine_type_id):
        return False
    return item.status == "received" if envelope.event == "procurement_received" else item.status in {"requested", "approved", "ordered"}


@safe_adapter
def notify(item, event):
    machine_id = item.resulting_machine_id
    if machine_id is None and item.source_pool_id:
        machine_id = item.source_pool.machine_id
    if machine_id is None and item.resulting_pool_id:
        machine_id = item.resulting_pool.machine_id
    context = {"makerspace": bag(name=item.makerspace.name), "event_name": event,
               "subject": bag(id=item.pk, name=item.name[:160])}
    return fanout(space=item.makerspace, feature="stock", stream="stock", event=event,
        kind=KIND, source=item.pk, version=version(item), subject=item,
        staff=content(render(item.makerspace, "stock", "staff", event, context)), staff_context=context,
        scope=NotificationScope(machine=machine_id, machine_type=item.machine_type_id),
        context={"to_buy_item_id": item.pk})


def register():
    register_source(KIND, NotificationSource(eligible))
