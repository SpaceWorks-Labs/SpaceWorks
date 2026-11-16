"""Personal notices added by lane L21a, one source module registered in the catalogue.

- `application_stage_advanced`: only when the event's per-event switch is on (default off).
- `attendance_confirmation` / `attendance_reminder`: "Are you still coming?", staff-sent.
- `crew_invited` / `crew_decided`: a staff-added crew place, and a sign-up decision.

Each live check re-reads its row: it must still exist, belong to the recipient and sit in a
servable space with events on. The copy names the event and links to the person's own
page; it never carries anyone else's details.
"""
from django.utils.translation import gettext, gettext_noop
from apps.integrations.notification_links import local_link
from apps.integrations.notification_outbox import emit

STAGE_SOURCE = "events.application_stage"
ATTENDANCE_SOURCE = "events.attendance"
CREW_SOURCE = "events.crew"
REPLY_SOURCE = "events.attendance_reply"


def _send(event, recipient_id, name, *, source, source_id, revision, subject, context, copy, tail):
    """`copy` returns (title, text); emit() runs it in the recipient's language."""
    from apps.accounts.models import User
    from apps.integrations.recipients_owners import eligible_owner
    if not eligible_owner(event.makerspace, recipient_id):
        return None
    return emit(makerspace=event.makerspace, recipient=User.objects.get(pk=recipient_id), feature="events",
                stream="events", event=name, audience="requester", dedup_key=f"ev:{source}:{source_id}:{name}:{revision}",
                source_kind=source, source_id=str(source_id), revision=str(revision)[:64], subject=subject,
                context={"event_id": event.pk, **context},
                rendered=lambda: dict(zip(("subject", "text"), copy()), html="",
                                      link=local_link(event.makerspace, "member", tail)))


def stage_advanced_notice(event, application, stage):
    from .models_participation import EventParticipationSettings
    if not EventParticipationSettings.for_event(event).stage_advanced_email:
        return None
    return _send(event, application.member_id, "application_stage_advanced", source=STAGE_SOURCE,
                 source_id=application.pk, revision=application.version, subject=application,
                 context={"application_id": application.pk},
                 copy=lambda: (gettext('Your application for {title} moved on').format(title=event.title),
                               gettext("Your application for %(title)s has moved on to the next review stage: %(stage)s.")
                               % {"title": event.title, "stage": stage.name}),
                 tail="events/history")


def attendance_notice(reply, name, revision):
    event = reply.event
    return _send(event, reply.registration.member_id, name, source=ATTENDANCE_SOURCE, source_id=reply.pk,
                 revision=revision, subject=reply.registration, context={"reply_id": reply.pk},
                 copy=lambda: (gettext('Are you still coming to {title}?').format(title=event.title),
                               gettext("Are you still coming to %(title)s? Please tell the organisers, so they can plan, and give "
                                       "your place to someone else if you cannot make it.") % {"title": event.title}),
                 tail=f"events/{event.pk}/attendance")


def reply_notice(reply):
    """Staff only: a registrant answered "not coming". Organisers act on it (a freed seat, a refund to
    assess, or a multi-ticket place left to them). No name, no note: the Emails tab lists those."""
    from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
    from apps.integrations.notification_links import local_link as link_to

    @safe_adapter
    def send():
        event = reply.event
        outcomes = {
            "released": gettext_noop("Their place was released."),
            "due_case": gettext_noop("Their paid place was cancelled and a refund is waiting for your decision."),
            "left_to_staff": gettext_noop("Their place is part of a multi-ticket order, so it is left to you."),
        }
        outcome_key = outcomes.get(reply.effect, gettext_noop("Their place was not changed."))
        staff = lambda: {  # noqa: E731 - built in each organiser's language by emit()
            "subject": gettext("Someone is not coming to %(title)s") % {"title": event.title},
            "text": gettext("A registrant answered \"No\" to the attendance check for %(title)s. %(outcome)s")
            % {"title": event.title, "outcome": gettext(outcome_key)},
            "link": link_to(event.makerspace, "admin", f"events?event={event.pk}")}
        return fanout(space=event.makerspace, feature="events", stream="events", event="attendance_replied",
                      kind=REPLY_SOURCE, source=reply.pk, version=revision(reply.replied_at, reply.effect),
                      subject=reply, staff=staff, rooms=False,
                      context={"reply_id": reply.pk, "event_id": event.pk})
    return send()


def crew_notice(crew, name):
    event = crew.event
    def copy():
        if name == "crew_invited":
            return (gettext("You are on the crew for %(title)s") % {"title": event.title},
                    gettext("The organisers added you to the crew for %(title)s. Your crew place is free.")
                    % {"title": event.title})
        if crew.state == "approved":
            return (gettext("Welcome to the crew for %(title)s") % {"title": event.title},
                    gettext("Your crew sign-up for %(title)s is approved.") % {"title": event.title})
        return (gettext("Your crew sign-up for %(title)s") % {"title": event.title},
                gettext("Thank you for offering to help with %(title)s. The crew is full this time.")
                % {"title": event.title})
    return _send(event, crew.member_id, name, source=CREW_SOURCE, source_id=crew.pk, revision=crew.version,
                 subject=crew, context={"crew_id": crew.pk}, copy=copy, tail="events/history")


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


def reply_eligible(envelope):
    from .models import EventAttendanceReply
    row = EventAttendanceReply.objects.select_related("event__makerspace").filter(
        pk=envelope.context.get("reply_id")).first()
    from apps.makerspaces.platform import feature_enabled, module_enabled
    from apps.makerspaces.servability import is_servable
    return bool(row and envelope.audience == "staff" and str(row.pk) == str(envelope.source_id)
                and row.answer == "no" and row.event.makerspace_id == envelope.makerspace_id
                and is_servable(row.event.makerspace) and module_enabled(row.event.makerspace, "events")
                and feature_enabled(row.event.makerspace, "events.attendance_confirmation"))


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(STAGE_SOURCE, NotificationSource(stage_eligible))
    register_source(ATTENDANCE_SOURCE, NotificationSource(attendance_eligible))
    register_source(CREW_SOURCE, NotificationSource(crew_eligible))
    register_source(REPLY_SOURCE, NotificationSource(reply_eligible))
