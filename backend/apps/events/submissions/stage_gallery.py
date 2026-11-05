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


def gallery_stage_allowed(event_id, snapshot):
    """The gallery takes final-stage work; an earlier stage only with S18 on, once it is published, and
    only for teams that passed its gate (all teams when it has none). Never eliminated teams' work."""
    from .stage_runtime import last_stage_id, published_shortlist, shortlist_applied
    if snapshot.stage_id is None or snapshot.stage_id == last_stage_id(event_id):
        return True
    stage = SubmissionStage.objects.filter(pk=snapshot.stage_id, event_id=event_id).first()
    if stage is None or not stage.public_after_publish:
        return False
    if not stage.shortlist_after:
        return shortlist_applied(stage) or _closed(stage)
    published = published_shortlist(stage)
    return published is not None and published.entries.filter(snapshot_id=snapshot.id).exists()


def _closed(stage):
    from django.utils import timezone
    from .stage_runtime import base_cutoff
    return timezone.now() > base_cutoff(stage, stage.event)


def final_stage_entries(event_id, rows):
    """Gallery entries holding final-stage work only (for readers such as people's choice voting, #181)."""
    from .models_stages import SnapshotStage
    from .stage_runtime import last_stage_id
    last = last_stage_id(event_id)
    if last is None:
        return rows
    early = SnapshotStage.objects.filter(snapshot__submission__event_id=event_id).exclude(stage_id=last)
    return rows.exclude(snapshot_id__in=early.values_list("snapshot_id", flat=True))
