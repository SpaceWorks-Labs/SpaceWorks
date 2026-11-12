"""Server-side draft autosave for composer campaigns (X41).

The composer saves while the organiser types. Each save is an ordinary versioned campaign
command: live `manage_registrations` authority, the broadcast gates, an idempotency key and
optimistic concurrency on `expected_version`, so two tabs never overwrite each other
silently. Only a version-2 DRAFT changes; a scheduled or sent campaign never does.
"""

from django.utils.translation import gettext
from django.db import models, transaction
from rest_framework.exceptions import NotFound

from apps.audit.services import record
from apps.events.broadcasts import authorize
from apps.events.models_broadcasts import EventBroadcast

from .broadcast_content import pack
from .broadcast_designs import require_design_allowed
from .broadcast_preview import campaign_command
from .commands import ProgrammeConflict

FIELDS = ("subject", "body", "statuses", "attendance", "design", "ctas")


def require_visible(campaign, actor):
    """A draft belongs to the person who started it; anyone else (superadmin included) gets a 404."""
    if campaign.status == EventBroadcast.Status.DRAFT and campaign.created_by_id != actor.pk:
        raise NotFound()
    return campaign


def visible_to(queryset, actor):
    """Sent and scheduled campaigns are shared staff history; drafts are private to their author."""
    return queryset.exclude(~models.Q(created_by_id=actor.pk), status=EventBroadcast.Status.DRAFT)


def own_draft(event, actor):
    """The one open composer draft this person has on the event, if any."""
    return (EventBroadcast.objects.filter(event=event, created_by=actor, render_schema_version=2,
                                          status=EventBroadcast.Status.DRAFT).order_by("-created_at", "-pk").first())


@transaction.atomic
def delete_draft(campaign, actor):
    """Discard the author's own draft. Only a draft can go; a scheduled or sent campaign is history."""
    row = EventBroadcast.objects.select_for_update().get(pk=campaign.pk, event_id=campaign.event_id)
    require_visible(row, actor)
    if row.status != EventBroadcast.Status.DRAFT:
        raise ProgrammeConflict("invalid_transition", gettext("Only a draft can be deleted."))
    record(actor, "event.broadcast_draft_deleted", makerspace=row.makerspace, target=row)
    row.delete()


def save_draft(campaign, actor, payload):
    draft = payload["draft"]

    def update(row, locked_actor):
        if row.status != EventBroadcast.Status.DRAFT or row.render_schema_version != 2:
            raise ProgrammeConflict("invalid_transition", gettext("Only a composer draft can be edited."))
        require_design_allowed(row.makerspace, draft["design"])
        from apps.events.services_broadcasts import validate_audience
        row.subject = draft["subject"]
        row.statuses = list(draft["statuses"])
        row.attendance = draft["attendance"]
        row.design = draft["design"]
        row.body = pack(draft["subject"], draft["body"], ctas=draft["ctas"], design=draft["design"])
        validate_audience(row)
        authorize(row, locked_actor)
        row.version += 1
        row.save(update_fields=["subject", "body", "statuses", "attendance", "design", "version", "updated_at"])
        record(locked_actor, "event.broadcast_draft_saved", makerspace=row.makerspace, target=row,
               meta={"version": row.version})
        return {"campaign_id": row.pk, "version": row.version}

    campaign_command(campaign, actor, "broadcast.draft", payload, update)
    result = EventBroadcast.objects.get(pk=campaign.pk, event_id=campaign.event_id)
    authorize(result, actor)
    return result
