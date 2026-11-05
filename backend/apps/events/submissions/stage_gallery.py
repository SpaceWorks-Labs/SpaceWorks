"""S7: a final-stage custom choice field marked public becomes a gallery filter (``field.<key>=<choice>``)."""
from rest_framework.exceptions import ValidationError

from .models_stages import SubmissionStage


def public_filters(stage):
    return [{"key": f["key"], "label": f["label"], "choices": list(f.get("choices", []))}
            for f in stage.custom_fields if f.get("type") == "choice" and f.get("visible_to") == "public"]


def filter_by_fields(event, rows, params):
    wanted = {key[len("field."):]: value for key, value in params.items() if key.startswith("field.") and value}
    if not wanted:
        return rows
    stage = SubmissionStage.objects.filter(event=event).order_by("-position").first()
    allowed = {f["key"]: f["choices"] for f in public_filters(stage)} if stage else {}
    for key, value in wanted.items():
        if key not in allowed or value not in allowed[key]:
            raise ValidationError({f"field.{key}": "Use a public choice field and one of its choices."})
    from apps.events.judging.ports import runtime
    keep = []
    for row in rows:
        answers = {a[0]: a[3] for a in runtime().snapshot(row.snapshot_id).answers if a[4] == "public"}
        if all(answers.get(key) == value for key, value in wanted.items()):
            keep.append(row.pk)
    return rows.filter(pk__in=keep)
