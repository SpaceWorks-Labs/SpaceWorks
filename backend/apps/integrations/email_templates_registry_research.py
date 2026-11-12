"""F3 templates: explicit fields, no model objects, contacts or provider handles.

Staff payment context deliberately omits amounts: chat uses the staff registry entry.
Only the requester's own payment email receives amount/currency fields.
"""
from django.utils.translation import gettext_noop

from .email_templates_registry_helpers import EmailTemplateRegistryEntry, bag


FAMILY_EVENTS = {
    "payments": ("charge_raised", "payment_due_soon", "payment_due_today", "payment_overdue",
                 "payment_received", "refund_issued", "payment_failed",
                 "refund_due_opened", "refund_request_received", "refund_request_approved",
                 "refund_request_declined", "refund_approval_failed",
                 # Lane L5: offline claims, maker-checker, capture flags, disputes.
                 "paid_claim_received", "paid_claim_confirmed", "paid_claim_rejected",
                 "settlement_awaiting_confirmation", "capture_flagged", "dispute_opened"),
    "membership": ("approved", "declined", "renewal_due", "lapsed", "renewal_failed", "awaiting_payment", "payment_due",
                   "renewed", "grace_started", "cancelled"),
    "stock": ("low_stock", "procurement_received", "to_buy_created"),
    "maintenance": ("due_soon", "overdue"),
    "certifications": ("granted", "revoked", "expiring", "expired"),
}

# Stock and maintenance are staff operational alerts. The research names financial,
# membership lifecycle and certification expiry communication to the affected member.
REQUESTER_EVENTS = {
    # Refund-case arrivals are staff work items; only the decision reaches the payer.
    "payments": frozenset(FAMILY_EVENTS["payments"]) - {
        "refund_due_opened", "refund_request_received", "refund_approval_failed", "paid_claim_received",
        "settlement_awaiting_confirmation", "capture_flagged", "dispute_opened"},
    "membership": frozenset(FAMILY_EVENTS["membership"]),
    "certifications": frozenset({"expiring", "expired"}),
}

SUBJECT_FIELDS = {
    "payments": ("id", "status"),
    "membership": ("id", "status"),
    "stock": ("id", "name"),
    "certifications": ("id", "name", "expires_at"),
}

STAFF_TEXT = {
    "payments": gettext_noop("Payment #{{ subject.id }}: {{ event_label }}. Status: {{ subject.status }}."),
    "membership": gettext_noop("Membership #{{ subject.id }}: {{ event_label }}. Status: {{ subject.status }}."),
    "stock": gettext_noop("Stock item #{{ subject.id }} ({{ subject.name }}): {{ event_label }}."),
    "maintenance": gettext_noop("Maintenance schedule #{{ schedule.id }} for {{ machine.name }}: "
                   "{{ event_label }}. Due: {{ schedule.next_due }}."),
    "certifications": gettext_noop("Machine access #{{ subject.id }} ({{ subject.name }}): "
                      "{{ event_label }}. Expiry: {{ subject.expires_at }}."),
}

REQUESTER_TEXT = {
    "payments": gettext_noop("Your payment #{{ subject.id }}: {{ event_label }}. "
                "Amount: {{ subject.amount }} {{ subject.currency }}. "
                "{% if subject.due_date %}Due: {{ subject.due_date }}. {% endif %}"
                "Review your payment history at {{ makerspace.name }}."),
    "membership": gettext_noop("Your membership at {{ makerspace.name }}: {{ event_label }}."),
    "certifications": gettext_noop("Your access to {{ subject.name }} at {{ makerspace.name }}: "
                      "{{ event_label }}. Expiry: {{ subject.expires_at }}."),
}


def build_entries():
    entries = {}
    for stream, events in FAMILY_EVENTS.items():
        for event in events:
            audiences = ["staff"]
            if event in REQUESTER_EVENTS.get(stream, ()):
                audiences.append("requester")
            for audience in audiences:
                names = [f"subject.{key}" for key in SUBJECT_FIELDS.get(stream, ())]
                sample = {
                    "makerspace": bag(name="Demo workshop"), "event_name": event,
                    "subject": bag(id=12, status="pending", name="Laser induction",
                                   expires_at="2026-11-10T12:00:00Z"),
                }
                if stream == "maintenance":
                    names = ["schedule.id", "schedule.next_due", "machine.name"]
                    sample.update(schedule=bag(id=12, next_due="2026-11-10"),
                                  machine=bag(name="Laser cutter"))
                if stream == "payments" and audience == "requester":
                    names += ["subject.amount", "subject.currency", "subject.due_date"]
                    sample["subject"] = bag(id=12, status="pending", amount="25.00", currency="USD", due_date="2026-11-10")
                text = STAFF_TEXT[stream] if audience == "staff" else REQUESTER_TEXT[stream]
                entries[(stream, audience, event)] = EmailTemplateRegistryEntry(
                    label=event.replace("_", " ").capitalize(),
                    description=f"{audience.capitalize()} notice for {stream}: {event}.",
                    fields=[{"name": name, "description": "Bounded event snapshot."}
                            for name in [*names, "makerspace.name", "event_name", "event_label"]],
                    default_subject=f"{stream.capitalize()}: {event.replace('_', ' ')}",
                    default_text=text, default_html="", sample_context=sample,
                )
    return entries
