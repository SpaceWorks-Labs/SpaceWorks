"""Server-side draft autosave for composer campaigns (X41).

The composer saves while the organiser types. Each save is an ordinary versioned campaign
command: live `manage_registrations` authority, the broadcast gates, an idempotency key and
optimistic concurrency on `expected_version`, so two tabs never overwrite each other
silently. Only a version-2 DRAFT changes; a scheduled or sent campaign never does.
"""

from apps.audit.services import record
from apps.events.broadcasts import authorize
from apps.events.models_broadcasts import EventBroadcast

from .broadcast_content import pack
from .broadcast_designs import require_design_allowed
from .broadcast_preview import campaign_command
from .commands import ProgrammeConflict

FIELDS = ("subject", "body", "statuses", "attendance", "design", "ctas")


def save_draft(campaign, actor, payload):
    draft = payload["draft"]

    def update(row, locked_actor):
        if row.status != EventBroadcast.Status.DRAFT or row.render_schema_version != 2:
            raise ProgrammeConflict("invalid_transition", "Only a composer draft can be edited.")
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
