"""Mentor Desk help alerts posted to team chat rooms (G9, `events.mentor_chat_alerts`).

A new help request is posted to the rooms this event's organisers chose (Telegram,
Slack, Discord or Mattermost destinations of the hosting space) -- but only while at least
one eligible mentor is on shift, i.e. the same live `recipients()` set the personal notice
uses. The message is outbound text only: no buttons and no decision surface (Telegram
stays accept-and-ignore inbound), no requester or team member names, just the category,
the team's alias, the priority and a link to Mentor Desk.

Every room send goes through `deliver_text_to_destination`, which keeps the channel's
module gate, credential check and daily quota; the space's quiet hours hold room posts
too. Each (intent, room) pair is posted at most once, recorded in the audit log with
the destination KIND only.
"""

import logging

from django.conf import settings
from django.utils import timezone, translation
from django.utils.translation import gettext, ngettext

from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.makerspaces.platform import feature_enabled

logger = logging.getLogger(__name__)
FEATURE = "events.mentor_chat_alerts"
ROOM_CHANNELS = ("telegram", "slack", "discord", "mattermost")


def routes(event):
    from apps.events.models_r2_l2 import MentorAlertRoute
    return (MentorAlertRoute.objects.filter(event=event, makerspace_id=event.makerspace_id,
                                            destination__makerspace_id=event.makerspace_id,
                                            destination__is_active=True,
                                            destination__channel__in=ROOM_CHANNELS)
            .select_related("destination").order_by("pk"))


def _already_posted(intent, destination):
    return AuditLog.objects.filter(
        makerspace_id=intent.makerspace_id, action="mentor.help_alert_routed",
        target_type="events.mentornotificationintent", target_id=str(intent.pk),
        meta__destination_id=destination.pk).exists()


def alert_text(event, payload, on_shift):
    from apps.integrations.notification_links import local_link
    link = local_link(event.makerspace, "admin", f"events/{event.pk}/mentor-desk")
    # EP-43: a room is shared by everyone in it, so the text uses the deployment's default language, not
    # the language of whichever request raised the alert.
    with translation.override(settings.LANGUAGE_CODE):
        mentors = ngettext("%(count)d mentor is", "%(count)d mentors are", on_shift) % {"count": on_shift}
        return gettext(
            "Mentor help needed at %(event)s: %(category)s for %(team)s (priority %(priority)s). "
            "%(mentors)s on shift. Open Mentor Desk: %(link)s") % {
            "event": event.title, "category": payload["category"], "team": payload["team_alias"],
            "priority": payload["priority"], "mentors": mentors, "link": link}


def post_help_alert(intent, event, payload, recipient_ids):
    """Called after the personal notice, outside row locks; never raises."""
    if intent.kind != "created" or not recipient_ids or not feature_enabled(event.makerspace, FEATURE):
        return 0
    from apps.integrations.dispatch_destination import deliver_text_to_destination
    from apps.integrations.quiet_hours import quiet_until
    posted = 0
    for route in routes(event):
        destination = route.destination
        try:
            if _already_posted(intent, destination):
                continue
            if quiet_until(event.makerspace, destination.channel, timezone.now()):
                outcome, error = False, "quiet_hours"
            else:
                outcome, error = deliver_text_to_destination(
                    event.makerspace, destination, text=alert_text(event, payload, len(recipient_ids)),
                    feature="events", event="mentor_help_alert", reference=f"help-{intent.pk}-{destination.pk}")
            record(None, "mentor.help_alert_routed", makerspace=event.makerspace, target=intent,
                   meta={"destination_id": destination.pk, "channel": destination.channel,
                         "delivered": bool(outcome), "error": error or ""})
            posted += int(bool(outcome))
        except Exception:
            logger.warning("mentor_help_room_alert_failed",
                           extra={"intent_id": intent.pk, "destination_id": destination.pk})
    return posted


def set_routes(event, actor, destination_ids):
    """Replace the event's room choice; every destination must be an active room of this space."""
    from rest_framework.exceptions import ValidationError
    from apps.events.services_write_boundary import write_boundary
    from apps.events.models_r2_l2 import MentorAlertRoute
    from apps.integrations.models_destinations import NotificationDestination
    wanted = sorted(set(destination_ids))
    rooms = set(NotificationDestination.objects.filter(
        pk__in=wanted, makerspace_id=event.makerspace_id, channel__in=ROOM_CHANNELS).values_list("pk", flat=True))
    if set(wanted) - rooms:
        raise ValidationError({"destination_ids": gettext("Choose chat rooms of this makerspace.")})
    with write_boundary(event, actor=actor):
        MentorAlertRoute.objects.filter(event=event).exclude(destination_id__in=wanted).delete()
        for pk in wanted:
            MentorAlertRoute.objects.get_or_create(event=event, destination_id=pk, defaults={
                "makerspace_id": event.makerspace_id, "created_by": actor})
        record(actor, "mentor.help_alert_routes_changed", makerspace=event.makerspace, target=event,
               meta={"count": len(wanted)})
    return wanted
