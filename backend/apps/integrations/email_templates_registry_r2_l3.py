"""Release-2 L3 card notices (member, programme and event cards; designs; card jobs).

The producers in `card_designs/notifications.py` render their own bodies; these entries
give every catalogue event both audiences in the template editor and a valid staff chat
body built only from staff-safe fields (never a check link or an extra).
"""
from django.utils.translation import gettext_noop

from .email_templates_registry_helpers import EmailTemplateRegistryEntry, bag

TEXT = {
    "card_issued": (gettext_noop("Your card from {{ makerspace.name }} is ready. Open My cards to see, save or download it."),
                    gettext_noop("Card #{{ subject.id }} was issued.")),
    "event_card_issued": (gettext_noop("Your event ID card is ready in My cards."), gettext_noop("Event card #{{ subject.id }} was issued.")),
    "programme_card_decided": (gettext_noop("There is news about your ID card request. Open My cards for details."),
                               gettext_noop("ID card request #{{ subject.id }}: {{ subject.status }}.")),
    "card_photo_requested": (gettext_noop("{{ makerspace.name }} asked for a new photo for your card. Your card stays valid."),
                             gettext_noop("A new card photo was requested for card #{{ subject.id }}.")),
    "card_design_pending": (gettext_noop("A card design is waiting for approval."),
                            gettext_noop("Card design #{{ subject.id }} is waiting for approval.")),
    "card_job_finished": (gettext_noop("Your card job finished."), gettext_noop("Card job #{{ subject.id }} finished: {{ subject.status }}.")),
}


def build_entries():
    entries = {}
    for event, (requester_text, staff_text) in TEXT.items():
        for audience in ("staff", "requester"):
            entries[("membership", audience, event)] = EmailTemplateRegistryEntry(
                label=event.replace("_", " ").capitalize(),
                description=f"{audience.capitalize()} notice for cards: {event}.",
                fields=[{"name": name, "description": "Bounded event snapshot."}
                        for name in ("makerspace.name", "event_name", "subject.id", "subject.status")],
                default_subject=f"Cards: {event.replace('_', ' ')}",
                default_text=requester_text if audience == "requester" else staff_text,
                default_html="",
                sample_context={"makerspace": bag(name="Demo workshop"), "event_name": event,
                                "subject": bag(id=12, status="approved")},
            )
    return entries
