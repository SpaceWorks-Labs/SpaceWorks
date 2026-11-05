"""Authorized receiving-project metadata, with live event pool accounting."""
from apps.events.judging.models_definitions import HackathonTrack, HackathonPrize
from .models_assets import EventAssetUsage
from .quota import GROUP_CAPS, MIB, MANAGED_ALLOWANCE


def descriptor(context):
    from apps.events.hackathons.admission_models import HackathonConfig
    config = HackathonConfig.objects.get(event=context.event)
    usage = EventAssetUsage.objects.filter(event=context.event).first()
    budget = usage.budget_bytes if usage else context.budget_bytes
    if context.managed:
        budget = min(MANAGED_ALLOWANCE, budget) if budget is not None else MANAGED_ALLOWANCE
    used, reserved = (usage.used_bytes, usage.reserved_bytes) if usage else (0, 0)
    from .models_projects import HackathonSubmission
    from .stage_projection import participant_stages
    project = HackathonSubmission.objects.filter(event=context.event, team_id=context.team_id).first()
    stages, active = participant_stages(context.event, project, context.team_id)  # #178: per-stage rules.
    return {"version": 1, "stages": stages, "active_stage_id": active, "timezone": context.event.timezone_name, "deadline": context.deadline, "opens_at": config.submission_opens_at,
        "grace_seconds": context.grace_seconds, "late_policy": context.late_policy,
        "upload_policy": {"name": config.upload_policy, "version": config.upload_policy_version},
        "budget": {"limit_bytes": budget, "used_bytes": used, "reserved_bytes": reserved,
                   "remaining_bytes": max(0, budget-used-reserved) if budget is not None else None},
        "slots": [{"group": key, "max_bytes": cap*MIB} for key, cap in GROUP_CAPS.items() if key != "resume"],
        "tracks": [{"id": row.pk, "label": row.name, "version": row.version, "form": row.form,
                    "criteria": row.criteria} for row in HackathonTrack.objects.filter(event=context.event).order_by("order", "pk")[:100]],
        "prizes": [{"id": row.pk, "label": row.name, "version": row.version, "form": row.form,
                    "track_id": row.track_id, "criteria": row.criteria}
                   for row in HackathonPrize.objects.filter(event=context.event).order_by("order", "pk")[:100]]}
