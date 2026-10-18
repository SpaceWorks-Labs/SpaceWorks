import json
from datetime import timedelta
from uuid import uuid4
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.contributions import commands
from apps.events.contributions.errors import ProgrammeError, check_version
from apps.events.contributions.ports import ports
from .models_rounds import MentorImportPreview


def preview(*, actor, event_id, payload):
    def mutate(event, locks):
        if payload["expected_version"] != 0:
            raise ProgrammeError("stale_version", "Use version zero for an import preview.")
        if not payload["rows"] or len(payload["rows"]) > 500:
            raise ProgrammeError("invalid_import", "Supply 1–500 explicit team mappings.", status=400)
        mapping = ports().teams.validate_import(event_id=event.pk, rows=payload["rows"])
        return commands.new_row(MentorImportPreview, event, actor=actor, token=uuid4(),
            mapping_sha256=commands.digest(mapping), mapping=json.dumps(mapping),
            expires_at=timezone.now() + timedelta(minutes=15), practice_run_id=payload.get("practice_run_id"))

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="teams.import_preview", feature="events.mentoring", permission="manage_team", mutate=mutate, status=201)


def commit(*, actor, event_id, payload):
    def mutate(event, locks):
        row = get_object_or_404(MentorImportPreview.objects.select_for_update(), event=event,
            actor=actor, token=payload["preview_token"])
        check_version(row, payload["expected_version"])
        if row.expires_at <= timezone.now():
            raise ProgrammeError("preview_expired", "Create a new import preview.", status=410)
        if row.committed_at:
            raise ProgrammeError("already_committed", "This mapping has already been imported.")
        if row.mapping_sha256 != payload["mapping_sha256"]:
            raise ProgrammeError("mapping_changed", "The import mapping changed.")
        mapping = json.loads(row.mapping)
        if commands.digest(ports().teams.validate_import(event_id=event.pk, rows=mapping)) != row.mapping_sha256:
            raise ProgrammeError("mapping_changed", "Revalidate the changed team mapping.")
        ports().teams.import_locked(event_id=event.pk, mapping=mapping,
            practice_run_id=str(row.practice_run_id) if row.practice_run_id else None, locks=locks)
        return commands.changed(row, committed_at=timezone.now())

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="teams.import_commit", feature="events.mentoring", permission="manage_team", mutate=mutate)
