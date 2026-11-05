"""The hackathon config's submission window and the stage plan stay one truth (#178).

The config keeps its window fields as a mirror of the plan (first opening, last deadline, grace,
late policy) for every reader of the overall window. Editing them through the config:
- with ONE stage ("Single submission") writes through to that stage, so today's control still works;
- with several stages is refused (``submission_window_by_stage``): each stage has its own window.
A config created after the stage migration gets its "Single submission" stage at once.
"""
from apps.audit.services import record

WINDOW = {"submission_opens_at": "opens_at", "submission_deadline": "deadline",
          "submission_grace_minutes": "grace_minutes", "late_policy": "late_policy"}


def changed_window(config, data):
    return sorted(key for key in WINDOW if key in data and data[key] != getattr(config, key))


def refuse_multi_stage(config, data):
    from .models_stages import SubmissionStage
    if config.pk and changed_window(config, data) and SubmissionStage.objects.filter(event_id=config.event_id).count() > 1:
        from apps.events.hackathons.admission_errors import fail
        fail("submission_window_by_stage", "This event has several submission stages. Edit each stage's window.",
             status=400)


def sync_after_save(config, actor, changed):
    """After the config saved: make its single stage match (or create it)."""
    from .stage_runtime import ensure_stages
    stages = ensure_stages(config.event, config)
    if len(stages) != 1 or not changed:
        return
    stage = stages[0]
    for key, field in WINDOW.items():
        setattr(stage, field, getattr(config, key))
    stage.version += 1
    stage.save()
    record(actor, "event.submission_stages.updated", makerspace=config.event.makerspace, target=config.event,
           meta={"event_id": config.event_id, "preset": "", "created": 0, "updated": 1, "deleted": 0,
                 "count": 1, "source": "config_window"})
