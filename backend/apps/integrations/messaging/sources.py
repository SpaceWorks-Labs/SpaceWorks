"""Persist domain identity, never a payload's contacts or notification text."""
from django.apps import apps
from django.core.exceptions import ValidationError

from apps.accounts import rbac
from apps.integrations.destinations import NotificationScope
from apps.integrations.notification_scope_contract import validate_notification_scope

# Priority matters: an event registration owns the notice, rather than its event.
SOURCES = {
    "request_id": ("hardware_request", "hardware_requests.HardwareRequest", "makerspace_id", "requester_id"),
    "machine_service_request_id": ("machine_service_request", "machines.MachineServiceRequest", "makerspace_id", "member_id"),
    "booking_id": ("booking", "bookings.Booking", "space__makerspace_id", "member_id"),
    "registration_id": ("registration", "events.EventRegistration", "event__makerspace_id", "member_id"),
    "event_id": ("event", "events.Event", "makerspace_id", None),
    "series_id": ("event_series", "events.EventSeries", "makerspace_id", None),
    "membership_request_id": ("membership_request", "makerspaces.MembershipRequest", "makerspace_id", "user_id"),
    "certification_grant_id": ("certification_grant", "machines.CertificationGrant", "certification_type__makerspace_id", "membership.user_id"),
    "term_id": ("membership_term", "makerspaces.MembershipTerm", "membership__makerspace_id", "membership.user_id"),
    "membership_id": ("membership", "makerspaces.MakerspaceMembership", "makerspace_id", "user_id"),
    "payment_id": ("payment", "payments.Payment", "makerspace_id", "member_id"),
    "to_buy_item_id": ("stock_item", "procurement.ToBuyItem", "makerspace_id", None),
    "schedule_id": ("schedule", "maintenance.MaintenanceSchedule", "machine__makerspace_id", None),
    "maintenance_log_id": ("maintenance_log", "maintenance.MaintenanceLog", "machine__makerspace_id", None),
    "machine_id": ("machine", "machines.Machine", "makerspace_id", None),
    "api_key_request_id": ("api_key_request", "apiclients.ApiKeyRequest", "makerspace_id", "requester_id"),
    "inventory_watch_id": ("inventory_watch", "inventory.InventoryWatch", "makerspace_id", "user_id"),
    "product_id": ("product", "inventory.InventoryProduct", "makerspace_id", None),
    "device_id": ("device", "devices.Device", "makerspace_id", None),
}
BY_TYPE = {entry[0]: entry for entry in SOURCES.values()}


def scope_snapshot(scope):
    data = {} if scope is None else {key: getattr(scope, key) for key in
        ("machine_id", "machine_type_id", "category_id") if getattr(scope, key) is not None}
    validate_notification_scope(data)
    return data


def source_identity(feature, payload):
    data = payload.data or {}
    # Hardware charge notices are about a loan, not the associated ledger row.
    if feature == "devices":
        device = (payload.context or {}).get("device")
        pk = getattr(device, "id", None)
        return ("device", str(pk)) if pk else ("", "")
    for key, entry in SOURCES.items():
        if data.get(key):
            return entry[0], str(data[key])
    return "", ""


def _attr(row, path):
    for key in path.split("."):
        row = getattr(row, key, None)
        if row is None:
            break
    return row


def current_source(delivery):
    if delivery.source_type == "messaging_test":
        return delivery.user if delivery.source_id == str(delivery.user_id) else None
    entry = BY_TYPE.get(delivery.source_type)
    if not entry or not delivery.source_id:
        return None
    try:
        model = apps.get_model(entry[1])
        return rbac.scope_notification_policy(model.objects.all(), makerspace_id=delivery.makerspace_id,
            field=entry[2]).filter(pk=delivery.source_id).first()
    except (LookupError, ValueError, ValidationError):
        return None


def current_scope(delivery, row):
    if delivery.source_type == "messaging_test":
        return {}
    if delivery.feature == "maintenance":
        machine = row if delivery.source_type == "machine" else row.machine
        return scope_snapshot(NotificationScope(machine=machine))
    if delivery.feature == "certifications":
        return scope_snapshot(NotificationScope(machine_type=row.certification_type.machine_type_id))
    if delivery.feature == "stock":
        machine_id = row.resulting_machine_id
        if machine_id is None and row.source_pool_id:
            machine_id = row.source_pool.machine_id
        if machine_id is None and row.resulting_pool_id:
            machine_id = row.resulting_pool.machine_id
        return scope_snapshot(NotificationScope(machine=machine_id, machine_type=row.machine_type_id))
    if delivery.feature == "bookings" and delivery.event == "restored":
        return scope_snapshot(NotificationScope(machine_type=row.space.machine_type_id))
    return {}


def owner_matches(delivery, row):
    if delivery.source_type == "inventory_watch":
        from apps.makerspaces.platform import feature_enabled
        return (row.user_id == delivery.user_id and delivery.makerspace.public_inventory_enabled
                and feature_enabled(delivery.makerspace, "inventory.notify_when_back")
                and row.product.is_public and not row.product.is_archived and row.product.available_quantity > 0)
    path = BY_TYPE[delivery.source_type][3]
    if delivery.source_type == "machine_service_request":
        return (row.member_id or row.requester_id) == delivery.user_id
    return bool(path and _attr(row, path) == delivery.user_id)


def projection_context(delivery, payload):
    """Fill adapters without template contexts from their validated domain row."""
    context = dict(payload.context or {})
    context["makerspace"] = delivery.makerspace
    source = current_source(delivery)
    if source is not None:
        if delivery.source_type == "payment":
            from apps.payments.notification_projections import payment_subject
            refund_id = (payload.data or {}).get("refund_id")
            refund = source.refunds.filter(pk=refund_id).first() if refund_id else None
            context["subject"] = payment_subject(source, audience=delivery.audience, refund=refund)
            return context
        if delivery.source_type == "machine_service_request" and delivery.feature == "printing":
            from apps.machines.service_printing_projection import printing_projection
            from apps.integrations.email_templates_registry_helpers import bag
            printed = printing_projection(source)
            context["print_request"] = bag(id=printed.id, status=printed.status, quantity=printed.quantity)
            return context
        name = {"hardware_request": "request", "machine_service_request": "print_request",
                "booking": "booking", "registration": "registration", "event": "event",
                "schedule": "schedule", "maintenance_log": "log", "machine": "machine",
                "api_key_request": "api_key_request", "device": "device"}.get(delivery.source_type, "subject")
        context.setdefault(name, source)
    return context
