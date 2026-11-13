"""Immutable device edges remain distinguishable across outage/recovery cycles."""
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.integrations.email_templates_registry_helpers import bag
from apps.operations.notifications_p2 import fanout, revision, safe_notification, scoped, staff_link, template
from apps.makerspaces.platform import module_enabled
from apps.hardware_requests.notification_projection import addressed_context
from .models import Device, DeviceEvent

SOURCE = "devices.state_edge"
EDGE_TYPES = {"offline": "offline_detected", "recovered": "recovered"}


def load(envelope):
    return scoped(DeviceEvent, envelope.makerspace_id).select_related(
        "device", "makerspace",
    ).filter(pk=envelope.source_id).first()


def eligible(envelope):
    edge = load(envelope)
    return bool(edge and envelope.audience == "staff"
        and edge.event_type == EDGE_TYPES.get(envelope.event)
        and edge.device.status == Device.Status.ACTIVE
        and module_enabled(edge.makerspace, "devices")
        and envelope.revision == revision(edge.pk, edge.created_at))


@safe_notification
def notify_device_state(makerspace, device, event, *, now):
    edge = scoped(DeviceEvent, makerspace.pk).filter(
        device=device, event_type=EDGE_TYPES[event],
    ).order_by("-created_at", "-pk").first()
    if edge is None:
        raise ValueError("Device state notification requires its immutable edge")
    context = {"device": bag(id=str(device.pk), name=edge.device_name, kind=device.kind,
        state=event, last_seen_at=device.last_seen_at, offline_since=device.offline_since), "now": now}
    rendered = template(makerspace, "devices", "staff", event, context, link=staff_link(makerspace, "devices"))
    return fanout(row=edge, space=makerspace, feature="devices", stream="devices", event=event,
        source_kind=SOURCE, revision=revision(edge.pk, edge.created_at), staff_body=rendered, staff_context=context,
        context=addressed_context(makerspace, "devices", event, "staff", context))


def register():
    register_source(SOURCE, NotificationSource(eligible))
