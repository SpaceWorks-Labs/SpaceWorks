"""Staff template contracts for notification events without an email template."""

from .email_templates_registry_helpers import EmailTemplateRegistryEntry, bag


EVENTS = {
    ("hardware_requests", "deposit_raised"): ("request.id", "request.status"),
    ("hardware_requests", "late_fee_raised"): ("request.id", "request.status"),
    ("hardware_requests", "back_available"): ("product.id", "product.name"),
    ("hardware_requests", "problem_report.filed"): ("problem_report_id",),
    ("api_access", "api_key_request_resolved"): ("request.id", "request.status"),
    ("api_access", "subdomain_request_resolved"): (),
    ("members", "joined"): ("subject.id", "subject.status"),
    ("members", "verified"): ("subject.id", "subject.status"),
    ("members", "vouched"): (),
    ("stock", "scheduled"): (),
    ("stock", "completed"): (),
    # Machine-service cancellation fans out to staff and rooms (notify_service); the
    # requester leg is an owner self-notice, so only the bounded summary is offered.
    ("printing", "cancelled"): (),
}

# These producers explicitly disable staff/room fan-out. Their personal content
# must not become selectable as a staff chat template just because an email
# registry entry exists for the same event.
PERSONAL_ONLY_EVENTS = frozenset({
    ("members", "broadcast"), ("members", "invitation"),
    ("api_access", "email.failed"), ("api_access", "scheduled_report"),
    ("payments", "document_issued"), ("presence", "expired"),
    # Queue-head "next" is an owner self-notice only (service_queue_notices); it never
    # reaches staff or rooms.
    ("printing", "next"),
})


def chat_only_entry(feature, event):
    names = EVENTS.get((feature, event))
    if names is None:
        return None
    return EmailTemplateRegistryEntry(
        label=event.replace("_", " ").capitalize(),
        description=f"Staff chat notice for {feature}: {event}.",
        fields=[{"name": name, "description": "Event snapshot."}
                for name in names] + [{"name": "makerspace.name", "description": "Makerspace name."}],
        default_subject=event.replace("_", " ").capitalize(),
        default_text="{{ makerspace.name }}: " + event.replace("_", " ") + ".",
        default_html="",
        sample_context={"makerspace": bag(name="Demo workshop"), "problem_report_id": 12,
                        "request": bag(id=12, status="pending"),
                        "product": bag(id=12, name="Torque wrench"),
                        "subject": bag(id=12, status="active")},
    )
