"""Seeded reviewer assignment for a stage: preview, then a fingerprint-checked apply.

BALANCED reuses the judging planner (minimum-cost flow, squared workload) with a floor of
one review; RANDOM orders each application's eligible reviewers by a hash of the seed. The
seed is stored, so the same stage, subjects, panel and seed always give the same plan. The
apply recomputes the plan under the event lock and refuses when its fingerprint differs
from the preview the staffer saw.
"""
import hashlib
import json
import secrets

from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.audit import services as audit

from apps.events.judging.assignment_planner import plan_assignments

from .admission_errors import fail
from .admission_models import HackathonApplication
from .admission_stage_models import AdmissionStage, AdmissionStageAssignment, AdmissionStageReviewer
from .admission_stages import current_stage, materialize_entry_locked, require_feature
from .admission_transactions import command

OPEN_STATES = ("submitted", "waitlisted")


def candidates(stage):
    """Undecided applications that stand in this stage, oldest submission first."""
    rows = HackathonApplication.objects.filter(event_id=stage.event_id, state__in=OPEN_STATES,
                                               cohort__isnull=True).order_by("submitted_at", "pk")
    return [row for row in rows if (current := current_stage(row)) is not None and current.pk == stage.pk]


def random_plan(application_ids, reviewer_ids, *, target, blocked, existing, seed):
    pairs, deficits, loads = [], {}, {reviewer: 0 for reviewer in reviewer_ids}
    for _, reviewer in existing:
        loads[reviewer] = loads.get(reviewer, 0) + 1
    for application in sorted(application_ids):
        have = sum(1 for app, _ in existing if app == application)
        ordered = sorted(reviewer_ids, key=lambda r: hashlib.sha256(f"{seed}:{application}:{r}".encode()).digest())
        for reviewer in ordered:
            if have >= target:
                break
            if (application, reviewer) in blocked or (application, reviewer) in existing:
                continue
            pairs.append((application, reviewer))
            loads[reviewer] += 1
            have += 1
        if have < target:
            deficits[application] = target - have
    return tuple(sorted(pairs)), deficits, loads


def plan(stage, *, seed, strategy):
    from .review_workflow import conflicted
    applications = candidates(stage)
    reviewer_ids = sorted(AdmissionStageReviewer.objects.filter(stage=stage, removed_at__isnull=True)
                          .values_list("reviewer_id", flat=True))
    existing = frozenset(AdmissionStageAssignment.objects.filter(stage=stage).exclude(
        state=AdmissionStageAssignment.State.RECUSED).values_list("application_id", "reviewer_id"))
    blocked = frozenset((app.pk, reviewer) for app in applications for reviewer in reviewer_ids
                        if conflicted(stage.event_id, reviewer, app))
    ids = [app.pk for app in applications]
    existing = frozenset(pair for pair in existing if pair[0] in ids and pair[1] in reviewer_ids)
    if not ids or not reviewer_ids:
        pairs, deficits, loads = (), {app: stage.reviews_per_application for app in ids}, {}
    elif strategy == AdmissionStage.Strategy.RANDOM:
        pairs, deficits, loads = random_plan(ids, reviewer_ids, target=stage.reviews_per_application,
                                             blocked=blocked, existing=existing, seed=seed)
    else:
        result = plan_assignments(ids, reviewer_ids, target_views=stage.reviews_per_application, blocked=blocked,
                                  existing=existing, seed=seed, minimum_views=1)
        pairs, deficits, loads = result.pairs, result.deficits, result.loads
    body = {"stage_id": stage.pk, "version": stage.version, "strategy": strategy, "seed": seed,
            "pairs": [list(pair) for pair in pairs]}
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"stage_id": stage.pk, "strategy": strategy, "seed": seed, "fingerprint": fingerprint,
            "pairs": [{"application_id": a, "reviewer_id": r} for a, r in pairs],
            "deficits": [{"application_id": a, "missing": n} for a, n in sorted(deficits.items())],
            "loads": [{"reviewer_id": r, "assigned": n} for r, n in sorted(loads.items())],
            "applications": len(ids)}


def preview(*, event, stage, seed=None, strategy=None):
    require_feature(event)
    return plan(stage, seed=seed or secrets.token_hex(8), strategy=strategy or stage.assignment_strategy)


def apply(*, event_id, stage_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"stage.assign:{stage_id}",
                 permission="review_applications") as ctx:
        require_feature(ctx.event)
        stage = get_object_or_404(AdmissionStage.objects.select_for_update(), pk=stage_id, event=ctx.event)
        if ctx.reference:
            return stage, ctx.reference.get("created", 0)
        if stage.state == AdmissionStage.State.CLOSED:
            fail("invalid_transition", "Reopen the stage before assigning reviewers.")
        result = plan(stage, seed=data["seed"], strategy=data["strategy"])
        if result["fingerprint"] != data["fingerprint"]:
            fail("plan_changed", "Applications or the panel changed since the preview. Preview again.")
        for pair in result["pairs"]:
            application = HackathonApplication.objects.select_for_update().get(pk=pair["application_id"])
            materialize_entry_locked(ctx, application, stage)
            AdmissionStageAssignment.objects.create(stage=stage, application=application,
                                                    reviewer_id=pair["reviewer_id"], plan_fingerprint=result["fingerprint"])
        stage.assignment_seed, stage.assignment_fingerprint = result["seed"], result["fingerprint"]
        stage.assignment_strategy, stage.assigned_at = result["strategy"], timezone.now()
        stage.version += 1
        stage.save()
        audit.record(actor, "event.admission_stage.assigned", makerspace=ctx.event.makerspace, target=stage,
                     meta={"event_id": ctx.event.pk, "stage_id": stage.pk, "position": stage.position,
                           "strategy": result["strategy"], "fingerprint": result["fingerprint"],
                           "assignments": len(result["pairs"]), "deficits": len(result["deficits"])})
        ctx.finish("admission_stage", stage.pk, created=len(result["pairs"]))
        return stage, len(result["pairs"])
