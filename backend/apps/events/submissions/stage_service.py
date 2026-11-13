"""The organiser's stage editor (#177, #178, #180): read the plan, or replace it in one command.

Replacing the ordered list adds, edits, removes and reorders stages at once. A stage that already
has submissions, a shortlist, an extension or a judging round can be edited and moved but never
removed; editing it never touches a frozen snapshot (each snapshot carries its own copy). The
hackathon config's window mirrors the plan (first opening, last deadline, grace and late policy) so
every reader of the overall window keeps working. Authority: the hackathon manager, exactly as for
the submission window.
"""
import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder

from apps.audit.services import record
from .errors import SubmissionError
from .models_stages import SubmissionStage, SubmissionStageEntry, StageExtension, StageShortlist
from .ports import boundary
from .stage_presets import PRESET_KEYS
from .stage_rules import check_plan, check_stage_quota
from .stage_runtime import STAGE_FIELDS, stages_for
from .workflow import canonical_digest


def fingerprint(stages):
    rows = [[s.pk, s.version, s.position] for s in stages]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def in_use(stage):
    from apps.events.judging.models_definitions import JudgingRound
    return (SubmissionStageEntry.objects.filter(stage=stage).exists() or StageShortlist.objects.filter(stage=stage).exists()
            or StageExtension.objects.filter(stage=stage).exists()
            or JudgingRound.objects.filter(submission_stage=stage).exists())


def replace(*, actor, event_id, data):
    stages_in = data["stages"]
    port = boundary()
    digest = canonical_digest({"stages": json.loads(json.dumps(data, cls=DjangoJSONEncoder)), "event": event_id})
    with port.locked(actor=actor, event_id=event_id, team_id=None, action="stage_edit") as ctx:
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(data["operation_id"]), digest=digest)
        if replay is not None:
            return replay
        from apps.events.hackathons.admission_models import HackathonConfig
        config = HackathonConfig.objects.select_for_update().get(event=ctx.event)
        stored = list(SubmissionStage.objects.select_for_update().filter(event=ctx.event).order_by("position"))
        if fingerprint(stored) != data["expected_fingerprint"]:
            raise SubmissionError("stale_version", 409)
        current = {s.pk: s for s in stored}  # Empty for a never-written plan: every row is created.
        if data.get("preset") and data["preset"] not in PRESET_KEYS:
            raise SubmissionError("invalid_stage", 400, reason="unknown_preset")
        check_plan(ctx.event, stages_in)
        check_stage_quota(ctx.event, len(stored), len(stages_in))
        kept = {row["id"] for row in stages_in if row.get("id")}
        if not kept <= set(current):
            raise SubmissionError("not_found", 404)
        removed = [s for pk, s in current.items() if pk not in kept]
        if any(in_use(stage) for stage in removed):
            raise SubmissionError("stage_in_use", 409)
        for stage in removed:
            stage.delete()
        created, changed = [], []
        for position, row in enumerate(stages_in, start=1):
            stage = current.get(row.get("id")) or SubmissionStage(event=ctx.event, position=position)
            values = {key: row.get(key, SubmissionStage._meta.get_field(key).get_default()) for key in STAGE_FIELDS}
            dirty = stage.pk is None or stage.position != position or any(getattr(stage, k) != v for k, v in values.items())
            if not dirty:
                continue
            for key, value in values.items():
                setattr(stage, key, value)
            stage.position = position
            if stage.pk is None:
                stage.save()
                created.append(stage.pk)
            else:
                stage.version += 1
                stage.save()
                changed.append(stage.pk)
        stages = stages_for(ctx.event.pk)
        _mirror(config, stages)
        record(actor, "event.submission_stages.updated", makerspace=ctx.event.makerspace, target=ctx.event,
               meta={"event_id": ctx.event.pk, "preset": data.get("preset") or "", "created": len(created),
                     "updated": len(changed), "deleted": len(removed), "count": len(stages)})
        result = projection(ctx.event, stages)
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(data["operation_id"]), digest=digest,
                           result=result)
        return result


def _mirror(config, stages):
    first, last = stages[0], stages[-1]
    window = {"submission_opens_at": first.opens_at, "submission_deadline": last.deadline,
              "submission_grace_minutes": last.grace_minutes, "late_policy": last.late_policy}
    if any(getattr(config, key) != value for key, value in window.items()):
        for key, value in window.items():
            setattr(config, key, value)
        config.version += 1
        config.save(update_fields=[*window, "version"])


def read(*, actor, event_id):
    with boundary().locked(actor=actor, event_id=event_id, team_id=None, action="admin_read") as ctx:
        return projection(ctx.event, stages_for(ctx.event.pk))


def projection(event, stages):
    from .stage_projection import staff_stage, editor_options
    if not stages:  # Never written: the virtual "Single submission" stage from the window (#178 default).
        from apps.events.hackathons.admission_models import HackathonConfig
        from .stage_presets import default_stage
        config = HackathonConfig.objects.filter(event=event).first()
        rows = [{"id": None, "position": 1, "version": 0, **default_stage(config)}] if config else []
        return {"event_id": event.pk, "fingerprint": fingerprint([]), "stages": rows, **editor_options(event)}
    return {"event_id": event.pk, "fingerprint": fingerprint(stages), "stages": [staff_stage(event, s) for s in stages],
            **editor_options(event)}
