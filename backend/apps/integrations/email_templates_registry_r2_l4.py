"""Release-2 L4 membership templates: the per-space erasure decision (X29).

Only the member who asked is notified; staff see the decision in the console. The staff
twin exists because every catalogue event carries both audiences in the editor.
"""

from .email_templates_registry_helpers import EmailTemplateRegistryEntry, bag

TEXT = {
    "erasure_approved": "{{ makerspace.name }} approved your request to erase your membership data. "
                        "Payment records and the audit log are kept, as the law requires.",
    "erasure_rejected": "{{ makerspace.name }} could not erase your membership data. "
                        "{% if decision.note %}Their note: {{ decision.note }}{% endif %}",
}


def build_entries():
    entries = {}
    for event, text in TEXT.items():
        for audience in ("staff", "requester"):
            entries[("membership", audience, event)] = EmailTemplateRegistryEntry(
                label=event.replace("_", " ").capitalize(),
                description=f"{audience.capitalize()} notice for membership: {event}.",
                fields=[{"name": name, "description": "Bounded event snapshot."}
                        for name in ("makerspace.name", "event_name", "subject.id", "subject.status", "decision.note")],
                default_subject=f"Membership: {event.replace('_', ' ')}",
                default_text=text if audience == "requester"
                else "Erasure request #{{ subject.id }}: {{ event_name }}.",
                default_html="",
                sample_context={"makerspace": bag(name="Demo workshop"), "event_name": event,
                                "subject": bag(id=12, status="approved"), "decision": bag(note="")},
            )
    return entries
