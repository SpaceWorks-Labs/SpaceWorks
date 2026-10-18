"""Already-locked optional form triggers; retry/open-limit suppression is harmless."""
from datetime import timedelta
from django.db import connection
from django.utils import timezone
from apps.audit.services import record
from apps.events.contributions import commands
from .models_queue import EventHelpRequest, EventHelpType
from .help_workflow import notice_locked


def fire_locked(*, actor, event, round, team_id, answers, locks):
    if not connection.in_atomic_block or locks.event_id != event.pk:
        raise RuntimeError("Round triggers require the owning workflow locks.")
    for rule in round.help_trigger_rules:
        value = answers.get(rule["question_id"])
        matches = value == rule["value"] if rule["op"] == "eq" else (
            isinstance(value, list) and rule["value"] in value)
        if not matches:
            continue
        key = commands.digest({"team": team_id, "round": round.pk, "trigger": rule["key"]})
        now = timezone.now()
        rows = EventHelpRequest.objects.filter(event=event, team_id=team_id, practice_run_id=round.practice_run_id)
        if rows.filter(dedup_key=key, created_at__gte=now - timedelta(seconds=60)).exists():
            continue
        help_type = EventHelpType.objects.get(event=event, key=rule["type_key"])
        if rows.filter(type=help_type, state__in=["open", "claimed"]).count() >= help_type.open_limit:
            continue
        row = commands.new_row(EventHelpRequest, event, team_id=team_id, type=help_type,
            raised_by=actor, origin="round", priority=help_type.priority,
            summary="Follow-up requested during a mentor round.", exclusive_until=now + timedelta(minutes=5),
            dedup_key=key, practice_run_id=round.practice_run_id,
            expires_at=min(event.ends_at, now + timedelta(minutes=help_type.expiry_minutes)))
        notice_locked(row, event, "created")
        record(actor, "event.help.round_triggered", makerspace=event.makerspace, target=row,
               meta={"round_id": round.pk, "event_id": event.pk})
