"""Personal notices added by lane L21a, one source module registered in the catalogue.

- `application_stage_advanced`: only when the event's per-event switch is on (default off).
- `attendance_confirmation` / `attendance_reminder`: "Are you still coming?", staff-sent.
- `crew_invited` / `crew_decided`: a staff-added crew place, and a sign-up decision.

Each live check re-reads its row: it must still exist, belong to the recipient and sit in a
servable space with events on. The copy names the event and links to the person's own
page; it never carries anyone else's details.
"""
from django.utils.translation import gettext
from apps.integrations.notification_links import local_link
from apps.integrations.notification_outbox import emit

STAGE_SOURCE = "events.application_stage"
ATTENDANCE_SOURCE = "events.attendance"
CREW_SOURCE = "events.crew"


def _send(event, recipient_id, name, *, source, source_id, revision, subject, context, title, text, tail):
    from apps.accounts.models import User
    from apps.integrations.recipients_owners import eligible_owner
    if not eligible_owner(event.makerspace, recipient_id):
        return None
    return emit(makerspace=event.makerspace, recipient=User.objects.get(pk=recipient_id), feature="events",
                stream="events", event=name, audience="requester", dedup_key=f"ev:{source}:{source_id}:{name}:{revision}",
                source_kind=source, source_id=str(source_id), revision=str(revision)[:64], subject=subject,
                context={"event_id": event.pk, **context},
                rendered={"subject": title, "text": text, "html": "",
                          "link": local_link(event.makerspace, "member", tail)})


def stage_advanced_notice(event, application, stage):
    from .models_participation import EventParticipationSettings
    if not EventParticipationSettings.for_event(event).stage_advanced_email:
        return None
    return _send(event, application.member_id, "application_stage_advanced", source=STAGE_SOURCE,
                 source_id=application.pk, revision=application.version, subject=application,
                 context={"application_id": application.pk},
                 title=gettext('Your application for {title} moved on').format(title=event.title),
                 text=f"Your application for {event.title} has moved on to the next review stage: {stage.name}.",
                 tail="events/history")


def attendance_notice(reply, name, revision):
    event = reply.event
    text = (f"Are you still coming to {event.title}? Please tell the organisers, so they can plan, and give "
            "your place to someone else if you cannot make it.")
    return _send(event, reply.registration.member_id, name, source=ATTENDANCE_SOURCE, source_id=reply.pk,
                 revision=revision, subject=reply.registration, context={"reply_id": reply.pk},
                 title=gettext('Are you still coming to {title}?').format(title=event.title), text=text,
                 tail=f"events/{event.pk}/attendance")


def crew_notice(crew, name):
    event = crew.event
    if name == "crew_invited":
        title, text = (f"You are on the crew for {event.title}",
                       f"The organisers added you to the crew for {event.title}. Your crew place is free.")
    elif crew.state == "approved":
        title, text = (f"Welcome to the crew for {event.title}", f"Your crew sign-up for {event.title} is approved.")
    else:
        title, text = (f"Your crew sign-up for {event.title}",
                       f"Thank you for offering to help with {event.title}. The crew is full this time.")
    return _send(event, crew.member_id, name, source=CREW_SOURCE, source_id=crew.pk, revision=crew.version,
                 subject=crew, context={"crew_id": crew.pk}, title=title, text=text, tail="events/history")


def _live(envelope, model, key, owner):
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    row = model.objects.select_related("event__makerspace").filter(pk=envelope.context.get(key)).first()
    return bool(row and str(row.pk) == str(envelope.source_id) and owner(row) == envelope.recipient_id
                and row.event.makerspace_id == envelope.makerspace_id and envelope.audience == "requester"
                and is_servable(row.event.makerspace) and module_enabled(row.event.makerspace, "events"))


def stage_eligible(envelope):
    from .models import HackathonApplication
    return _live(envelope, HackathonApplication, "application_id", lambda row: row.member_id)


def attendance_eligible(envelope):
    from .models import EventAttendanceReply
    return _live(envelope, EventAttendanceReply, "reply_id", lambda row: row.registration.member_id)


def crew_eligible(envelope):
    from .models import EventCrewMember
    return _live(envelope, EventCrewMember, "crew_id", lambda row: row.member_id)


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(STAGE_SOURCE, NotificationSource(stage_eligible))
    register_source(ATTENDANCE_SOURCE, NotificationSource(attendance_eligible))
    register_source(CREW_SOURCE, NotificationSource(crew_eligible))
