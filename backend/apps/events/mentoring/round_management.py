from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from apps.events.contributions import commands
from apps.events.contributions.errors import ProgrammeError, check_version
from apps.events.contributions.ports import ports
from apps.events.contributions.management_workflow import _valid, _zero
from .models_rounds import MentorRound


def save(*, actor, event_id, payload, round_id=None):
    schema = ports().forms.validate_schema(schema=payload["form_schema"]) if "form_schema" in payload else None
    if schema and any(q.get("type") in ("date_of_birth", "age_at_event") for q in schema.get("questions", [])):
        raise ValidationError({"form_schema": "Mentor visits cannot collect a team member's DOB or age."})

    def mutate(event, locks):
        row = get_object_or_404(MentorRound.objects.select_for_update(), pk=round_id, event=event) if round_id else (
            MentorRound(event=event, makerspace_id=event.makerspace_id))
        check_version(row, payload["expected_version"]) if round_id else _zero(payload)
        if row.state != "draft":
            raise ProgrammeError("round_locked", "A started round cannot change its form or policy.")
        for key, value in payload.items():
            if key not in ("operation_id", "expected_version", "form_schema"):
                setattr(row, key, value)
        if schema is not None:
            row.form_schema = schema
            row.form_schema_version = row.form_schema.get("revision", 1)
        questions = {q["id"] for q in row.form_schema.get("questions", [])}
        if set(row.note_keys) & set(row.rating_keys) or (set(row.note_keys) | set(row.rating_keys)) - questions:
            raise ValidationError({"note_keys": "Use distinct existing note and rating question IDs."})
        from .models_queue import EventHelpType
        keys = set()
        for rule in row.help_trigger_rules:
            if (set(rule) != {"key", "question_id", "op", "value", "type_key"} or
                not isinstance(rule["key"], str) or not 1 <= len(rule["key"]) <= 40 or rule["key"] in keys or
                rule["question_id"] not in questions or rule["op"] not in ("eq", "contains") or
                not isinstance(rule["value"], (str, bool)) or
                not EventHelpType.objects.filter(event=event, key=rule["type_key"]).exists()):
                raise ValidationError({"help_trigger_rules": "Use distinct bounded rules over existing questions and help types."})
            keys.add(rule["key"])
        if row.opens_at is None or row.closes_at is None or not event.starts_at <= row.opens_at < row.closes_at <= event.ends_at:
            raise ValidationError({"opens_at": "Choose a round window inside the event."})
        if round_id:
            row.version += 1
        _valid(row)
        row.save()
        return row

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="round.save", feature="events.mentor_rounds", permission="manage_team", mutate=mutate,
        status=200 if round_id else 201)
