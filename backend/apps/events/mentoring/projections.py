from datetime import timedelta
from django.utils import timezone
from apps.events.contributions.api_common import envelope
from apps.events.contributions.ports import ports
from .models_queue import EventHelpRequest
from . import policy


def help_request(row, *, actor, event, detail=False, member=False):
    own_claim = False
    if member:
        allowed = ["comment", "cancel"] if row.state in ("open", "claimed") else ["reopen"] if row.state == "resolved" else []
    elif policy.queue_manager(actor, event):
        allowed = ["assign"] if row.state in ("open", "claimed") else ["reopen"] if row.state == "resolved" else []
        if row.state == "claimed":
            allowed.extend(["release", "resolve", "comment"])
    else:
        mentor, _ = policy.mentor_for(actor, event)
        own_claim = row.claimed_by_id == mentor.pk
        allowed = ["release", "resolve", "comment"] if own_claim else ["claim"] if row.state == "open" else []
    data = {**envelope(row, allowed), "origin": row.origin,
        "team_alias": ports().teams.alias(event_id=event.pk, team_id=row.team_id),
        "category": row.type.label, "priority": row.priority, "zone": row.structured_zone}
    if member or detail:
        data.update(team_id=row.team_id, origin=row.origin, raised_by_role_assignment_id=row.raised_by_role_assignment_id)
    if detail:
        # Caller must enforce current-assignee/manager or own-team access first.
        data["summary"] = row.summary
    if member:
        data["position"] = EventHelpRequest.objects.filter(event=event, state="open",
            practice_run_id=row.practice_run_id, created_at__lte=row.created_at).count() if row.state == "open" else None
        # A measured estimate is omitted until there are five completed responses.
        completed = EventHelpRequest.objects.filter(event=event, practice_run_id__isnull=True,
            first_claimed_at__isnull=False, created_at__gte=timezone.now() - timedelta(hours=4))[:100]
        waits = [(item.first_claimed_at - item.created_at).total_seconds() for item in completed]
        data["wait_estimate"] = f"Recent first response: {round(sum(waits) / len(waits) / 60)} min" if len(waits) >= 5 else "Not enough recent data for an estimate"
    return data


def comment(row):
    return {"id": row.pk, "help_id": row.request_id, "created_at": row.created_at,
            "body": row.body, "origin": row.origin, "request_version": row.request.version}


def booking(row):
    return {**envelope(row, ["cancel"] if row.state == "booked" else []), "slot_id": row.slot_id, "team_id": row.team_id}


def lease(row):
    return {**envelope(row), "state": "active" if row.expires_at > timezone.now() else "expired",
        "lease_uuid": row.lease_uuid, "generation": row.generation,
        "expires_at": row.expires_at, "heartbeat_at": row.heartbeat_at, "team_id": row.team_id, "round_id": row.round_id}


def round_row(row):
    return {**envelope(row), **{key: getattr(row, key) for key in (
        "index", "key", "label", "opens_at", "closes_at", "form_schema", "note_keys")}}
