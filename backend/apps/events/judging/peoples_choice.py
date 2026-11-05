"""People's choice (#181 S3): the per-event settings and the voting state every surface shares.

An extra award beside judging, never a replacement: nothing here reads or writes rounds, scores or
judged results. No config row means the award is off for that event (new events start off). The
whole surface is behind ``events.peoples_choice`` (which needs ``events.project_gallery``): off
means 404 and the data is kept.
"""

from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from .boundary import command, mutation, notice
from .errors import ProgrammeError
from .feature import PEOPLES_CHOICE, require_capability
from .models_definitions import HackathonPrize
from .models_peoples_choice import PeoplesChoiceConfig, PeoplesChoiceResult, PeoplesChoiceVote
from .ports import runtime
from .serializers import validated
from .serializers_peoples_choice import PeoplesChoiceConfigInput, PeoplesChoiceConfigRead

FIELDS = ("enabled", "audience", "opens_at", "closes_at", "open_email")
DEFAULT_NAME = "People's choice"


def config_for(event):
    return PeoplesChoiceConfig.objects.select_related("prize").filter(event=event).first()


def result_for(event):
    return PeoplesChoiceResult.objects.filter(event=event).first()


def state(config, result, now=None):
    """off | scheduled | open | closed | published. Publishing ends voting for good."""
    now = now or timezone.now()
    if result is not None:
        return "published"
    if config is None or not config.enabled:
        return "off"
    if config.opens_at and now < config.opens_at:
        return "scheduled"
    if config.closes_at and now >= config.closes_at:
        return "closed"
    return "open"


def require_live(event):
    """The award exists only on a hackathon with the gallery on and the capability on."""
    runtime().require_programme(event, gallery=True)
    require_capability(event, PEOPLES_CHOICE)


def staff_event(actor, event_id):
    from apps.events import event_authority
    event = event_authority.get_event(actor, event_id, "manage_hackathon")
    require_live(event)
    return event


def window(config):
    if config is None:
        return {"audience": "members", "opens_at": None, "closes_at": None}
    return {"audience": config.audience, "opens_at": config.opens_at, "closes_at": config.closes_at}


def projection(event):
    config, result = config_for(event), result_for(event)
    current = state(config, result)
    ballots = PeoplesChoiceVote.objects.filter(event=event, voided_at__isnull=True).count()
    actions = [] if result else ["edit"] + (["publish"] if current == "closed" else [])
    return {"id": config.pk if config else 0, "event_id": event.pk, "version": config.version if config else 0,
            "enabled": bool(config and config.enabled), **window(config),
            "prize_id": config.prize_id if config else None,
            "prize_name": config.prize.name if config and config.prize_id else None,
            "open_email": bool(config and config.open_email), "state": current, "ballots": ballots,
            "allowed_actions": actions}


def read(event_id, *, actor):
    return projection(staff_event(actor, event_id))


def _changes(event, row, values):
    changes = {key: values[key] for key in FIELDS if key in values and values[key] != getattr(row, key)}
    if "prize_id" in values and values["prize_id"] != row.prize_id:
        prize = values["prize_id"]
        if prize is not None and not HackathonPrize.objects.filter(event=event, pk=prize).exists():
            raise ValidationError({"prize_id": "Choose a prize of this event."})
        changes["prize_id"] = prize
    opens = changes.get("opens_at", row.opens_at)
    closes = changes.get("closes_at", row.closes_at)
    if opens and closes and closes <= opens:
        raise ValidationError({"closes_at": "Voting must close after it opens."})
    return changes


def update(event_id, *, actor, data):
    values = validated(PeoplesChoiceConfigInput, data, partial=True)
    with mutation(event_id, actor, gallery=True) as (event, _):
        require_capability(event, PEOPLES_CHOICE)

        def run():
            row = PeoplesChoiceConfig.objects.select_for_update().filter(event=event).first()
            if (row.version if row else 0) != values["expected_version"]:
                raise ProgrammeError("stale_version", "This item changed.", current_version=row.version if row else 0)
            if result_for(event) is not None:
                raise ProgrammeError("already_published", "The People's choice result is published; its settings are final.")
            was_on = bool(row and row.enabled)
            row = row or PeoplesChoiceConfig(event=event, version=0)
            changes = _changes(event, row, values)
            for key, value in changes.items():
                setattr(row, key, value)
            row.version += 1
            row.save()
            record(actor, "event.peoples_choice.updated", makerspace=event.makerspace, target=row,
                   meta={"event_id": event.pk, "fields": sorted(changes)})
            if row.enabled and not was_on and row.open_email:
                notice(event, "peoples_choice_open", row.pk, row.version)
            # The command receipt stores this response as JSON, so it is serialized first.
            return PeoplesChoiceConfigRead(projection(event)).data
        return command(event, actor, values, path="peoples-choice", run=run)


def attended(event, member_id):
    from apps.events.models import EventRegistration
    return EventRegistration.objects.filter(event=event, member_id=member_id,
                                            status=EventRegistration.Status.ATTENDED).exists()


def notice_recipients(row):
    """Voting-open notice: registrants (or, for an attendees-only award, checked-in attendees).

    Rechecked at send: the award must still be on, unpublished and the same configuration.
    """
    from apps.events.models import EventRegistration
    config = config_for(row.event)
    if (config is None or config.pk != row.source_id or config.version != row.revision
            or state(config, result_for(row.event)) not in ("scheduled", "open")):
        return ()
    statuses = ([EventRegistration.Status.ATTENDED] if config.audience == "attendees"
                else [EventRegistration.Status.REGISTERED, EventRegistration.Status.ATTENDED])
    return tuple(sorted(set(EventRegistration.objects.filter(
        event=row.event, status__in=statuses, member__isnull=False).values_list("member_id", flat=True))))


def public_gallery_event(event):
    """The award follows the public gallery: a member route may only vote on a publicly visible event."""
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    space = event.makerspace
    if (not event.is_public or event.page_state != "live" or event.status not in ("published", "completed")
            or not is_servable(space) or not space.public_site_enabled or not module_enabled(space, "events")):
        raise Http404
