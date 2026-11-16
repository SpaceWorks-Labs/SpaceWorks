"""Pay-window notices (parity E-B5, C22): the member's 24-hour window opening and running out.

Account notices only (envelopes, the member's chosen channels). The live check re-reads the registration: it
must still exist, belong to the recipient and sit in a servable space with events on.
"""
from django.utils import timezone

from apps.integrations.notification_links import local_link
from apps.integrations.notification_outbox import emit
from apps.integrations.fanout_jobs import deferred_fanout

SOURCE = "events.pay_window"
EVENTS = ("pay_window_opened", "pay_window_expired")


def _copy(registration, event_name):
    title = registration.event.title
    if event_name == "pay_window_opened":
        until = timezone.localtime(registration.pay_by).strftime("%d %b %Y %H:%M") if registration.pay_by else ""
        return (f"Pay to keep your place at {title}",
                f"Your place at {title} is held until {until}. Pay before then or it goes to the next person.")
    return (f"Your place at {title} was released",
            f"The payment window for {title} ran out, so your place was given to the next person. "
            "You can register again while places last.")


@deferred_fanout()
def pay_window_notice(registration, event_name):
    from apps.integrations.recipients_owners import eligible_owner
    event = registration.event
    if event_name not in EVENTS or not eligible_owner(event.makerspace, registration.member_id):
        return None
    subject, text = _copy(registration, event_name)
    return emit(makerspace=event.makerspace, recipient=registration.member, feature="events", stream="events",
                event=event_name, audience="requester", dedup_key=f"ev:paywin:{registration.pk}:{event_name}:{registration.version}",
                source_kind=SOURCE, source_id=str(registration.pk), revision=str(registration.version),
                subject=registration, context={"registration_id": registration.pk, "notice": event_name},
                rendered={"subject": subject, "text": text, "html": "",
                          "link": local_link(event.makerspace, "member", f"events/{event.public_token}")})


def eligible(envelope):
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    from .models import EventRegistration
    row = EventRegistration.objects.select_related("event__makerspace").filter(
        pk=envelope.context.get("registration_id")).first()
    return bool(row and str(row.pk) == str(envelope.source_id) and row.member_id == envelope.recipient_id
                and row.event.makerspace_id == envelope.makerspace_id and envelope.audience == "requester"
                and is_servable(row.event.makerspace) and module_enabled(row.event.makerspace, "events"))


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(SOURCE, NotificationSource(eligible))
