"""Reviewed scalar projections layered over the existing email event catalogue.

No email body is reused: those contain names, contacts, tokens and free text.
Unmapped events have no projection and therefore no addressed delivery.
"""
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.integrations.email_templates_registry import get_entry
from apps.integrations.notification_catalog import FEATURE_EVENTS

STREAMS = {"hardware_requests": "hardware", "members": "membership", "api_access": "api"}
AUDIENCES = {"member": "requester", "staff": "staff"}
HARDWARE_MEMBER_EVENTS = {
    "submitted": "request_received", "accepted": "request_accepted", "rejected": "request_rejected",
    "issued": "request_issued", "returned": "request_returned", "return_reminder": "return_reminder",
    "partially_returned": "request_returned", "closed_with_issue": "request_returned",
}
REVIEWED_KEYS = {
    "hardware_requests": ("request.id", "request.status", "request.return_due_at"),
    "printing": ("print_request.id", "print_request.status", "print_request.quantity"),
    "events": ("event.id", "event.status", "event.when", "registration.id", "registration.status"),
    "bookings": ("booking.id", "booking.status", "booking.when"),
    "maintenance": ("machine.id", "schedule.id", "schedule.next_due", "schedule.is_active", "log.id"),
    "members": ("request.id", "subject.id", "subject.status"),
    "payments": ("subject.id", "subject.status", "subject.amount", "subject.currency", "subject.due_date"),
    "stock": ("subject.id",),
    "certifications": ("subject.id", "subject.expires_at"),
    "devices": ("device.id", "device.status"),
}
# These families emit member inbox notices; operational stock/maintenance/devices do not.
MEMBER_FAMILIES = frozenset({"hardware_requests", "printing", "events", "bookings", "members", "payments", "certifications", "api_access"})
# Existing inbox adapters with no editable email registry entry. Only their reviewed
# identifiers are admitted; no adapter body, API label or resolution note is reused.
INBOX_ONLY_PROJECTIONS = {
    ("hardware_requests", "deposit_raised", audience): ("makerspace.name", "request.id")
    for audience in ("member", "staff")
}
INBOX_ONLY_PROJECTIONS.update({
    ("hardware_requests", "late_fee_raised", audience): ("makerspace.name", "request.id")
    for audience in ("member", "staff")
})
# Lane L15: staff-only loan charge notices (the payer's notice is the ledger's charge_raised).
INBOX_ONLY_PROJECTIONS.update({
    ("hardware_requests", event, "staff"): ("makerspace.name", "request.id")
    for event in ("rental_raised", "damage_charged", "lost_charged", "fees_waived")
})
# Lane L16: the technician send binds an approved WhatsApp template naming the space only.
INBOX_ONLY_PROJECTIONS[("maintenance", "repair_dispatched", "staff")] = ("makerspace.name",)
INBOX_ONLY_PROJECTIONS.update({
    ("hardware_requests", "back_available", "member"): ("makerspace.name",),
    ("api_access", "api_key_request_resolved", "member"): ("makerspace.name", "api_key_request.id", "api_key_request.status"),
    ("api_access", "api_key_request_resolved", "staff"): ("makerspace.name", "api_key_request.id", "api_key_request.status"),
})


def email_event(feature, event, audience):
    if audience not in AUDIENCES or event not in FEATURE_EVENTS.get(feature, ()) or event == "broadcast":
        return None
    if audience == "member" and feature not in MEMBER_FAMILIES:
        return None
    key = HARDWARE_MEMBER_EVENTS.get(event) if feature == "hardware_requests" and audience == "member" else event
    if feature == "hardware_requests" and event == "overdue_escalated" and audience == "staff":
        key = "return_reminder"
    return (STREAMS.get(feature, feature), AUDIENCES[audience], key) if key else None


def allowed_keys(feature, event, audience):
    if (feature, event, audience) in INBOX_ONLY_PROJECTIONS:
        return INBOX_ONLY_PROJECTIONS[(feature, event, audience)]
    mapped = email_event(feature, event, audience)
    entry = get_entry(*mapped) if mapped else None
    if entry is None:
        return None
    declared = {item["name"] for item in entry.fields}
    reviewed = ("makerspace.name", *REVIEWED_KEYS.get(feature, ()))
    return tuple(key for key in reviewed if key in declared)


PROJECTION_KEYS = {(feature, event, audience): keys
    for feature, events in FEATURE_EVENTS.items() for event in events for audience in AUDIENCES
    if (keys := allowed_keys(feature, event, audience)) is not None}
EVENT_NAME_MAPPING = {key: email_event(*key) for key in PROJECTION_KEYS}
SMS_DEFAULT_TEXTS = {key: "{makerspace.name}: " + key[0].replace("_", " ") + " " + key[1].replace("_", " ")
                     + ". Please check your account." for key in PROJECTION_KEYS}


def project_context(feature, event, audience, context):
    keys = PROJECTION_KEYS.get((feature, event, audience))
    if keys is None:
        raise ValidationError("This lifecycle event/audience has no reviewed messaging projection.")
    result = {}
    for key in keys:
        value = context
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else getattr(value, part, None)
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        if value is None or isinstance(value, (str, int, float, bool)):
            result[key] = value[:500] if isinstance(value, str) else value
    return result


def render_sms(feature, event, audience, context):
    key = (feature, event, audience)
    if key not in SMS_DEFAULT_TEXTS or context.keys() - set(PROJECTION_KEYS[key]):
        raise ValidationError("Unreviewed messaging context.")
    return SMS_DEFAULT_TEXTS[key].replace("{makerspace.name}", str(context.get("makerspace.name") or "SpaceWorks"))
