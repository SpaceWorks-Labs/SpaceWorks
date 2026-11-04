"""Audited round transitions and deterministic, conflict-aware assignment planning."""

from django.utils import timezone

from .assignment_planner import plan_assignments
from .boundary import audit, changed, command, envelope, mutation, notice, owned
from .conflicts import eligible
from .errors import ProgrammeError, invalid
from .models_definitions import JudgingRound
from .models_scoring import JudgeAssignment, JudgingReason, JudgingRoundProject
from .ports import runtime
from .pairwise_ranking import DEFAULTS, PAIRWISE_VERSION
from .pairwise_projection import require_pairwise
from .pairwise_workflow import seed_locked
from .projections import round_calculation
from .serializers import AssignInput, CommandInput, FinalizeRoundInput, validated


def transition(event_id, round_id, *, actor, action, data):
    schema = FinalizeRoundInput if action == "finalize" else CommandInput
    values = validated(schema, data)
    with mutation(event_id, actor, permission=None if action == "finalize" else "manage_hackathon") as (event, _):
        def run():
            round = owned(JudgingRound, event_id, round_id, expected=values["expected_version"])
            if round.mode == "pairwise":
                require_pairwise(event, hide=False)
            if action == "open":
                _open(round, event)
            elif action == "close" and round.state == "open":
                round.state = "closed"
            elif action == "finalize" and round.state == "closed":
                calculation = round_calculation(round)
                if not calculation["coverage_complete"]:
                    reason = values.get("coverage_exception_reason")
                    if not reason:
                        raise ProgrammeError("incomplete_coverage", "Every project needs the required nonconflicted submitted views.")
                    round.coverage_exception = JudgingReason.objects.create(
                        event=event, makerspace_id=event.makerspace_id, actor=actor, body=reason)
                round.state = "finalized"
            else:
                invalid()
            return changed(event, actor, f"round_{action}", round)
        return command(event, actor, values, path=f"judging-rounds/{round_id}/{action}", run=run)


def _open(round, event):
    if round.state != "draft":
        invalid()
    now = timezone.now()
    if (round.opens_at and now < round.opens_at) or (round.closes_at and now >= round.closes_at):
        invalid("This round is outside its judging window.")
    criteria = list(round.criteria.order_by("priority", "pk"))
    if round.mode == "weighted_1_5" and not criteria:
        invalid("A weighted round needs an anchored rubric.")
    draft = round.configuration or {}
    round.configuration = {"mode": round.mode, "min_reviews": round.min_reviews,
                           "minutes_per_view": round.minutes_per_view, "judging_minutes": round.judging_minutes,
                           "normalization": round.normalization, "criteria_revision": round.criteria_revision,
                           "criteria": [{"key": c.key, "label": c.label, "weight": str(c.weight),
                                         "anchors": c.anchors} for c in criteria]}
    if round.mode == "pairwise":
        round.algorithm_version = PAIRWISE_VERSION
        round.configuration |= {"guidance": draft.get("guidance", ""), "pairwise": {
            **DEFAULTS, **draft.get("pairwise", {}), "seed": f"round-{round.pk}"}}
    snapshots = [s for s in runtime().snapshots(round.event_id) if s.event_id == round.event_id and s.eligible and s.current]
    if not snapshots:
        invalid("There are no eligible frozen submissions.")
    for snapshot in snapshots:
        JudgingRoundProject.objects.create(round=round, snapshot_id=snapshot.id)
    round.state = "open"
    if round.mode == "pairwise":
        seed_locked(event, round)


def assign(event_id, round_id, *, actor, data):
    values = validated(AssignInput, data)
    with mutation(event_id, actor) as (event, _):
        def run():
            round = owned(JudgingRound, event_id, round_id, expected=values["expected_version"])
            if round.state != "open":
                invalid()
            if round.mode == "pairwise":
                invalid("Pairwise rounds pick each judge's next project as they judge; there is no batch to plan.")
            judges = [runtime().judge(pk) for pk in values["judge_role_assignment_ids"]]
            if any(not j.active or j.event_id != event_id for j in judges):
                from django.http import Http404
                raise Http404
            if len({j.member_id for j in judges}) != len(judges):
                invalid("Each judge must be a distinct member.")
            snapshots = [runtime().snapshot(pk) for pk in round.projects.values_list("snapshot_id", flat=True)]
            snapshots = [s for s in snapshots if s.current and s.eligible and s.event_id == event_id]
            previous = list(round.assignments.all())
            blocked = {(s.id, j.role_assignment_id) for s in snapshots for j in judges if not eligible(j, s, round)
                       or (values["strategy"] == "room" and j.room != s.room)}
            existing = set()
            valid_judges = {j.role_assignment_id for j in judges}
            ids = {s.id for s in snapshots}
            snapshot_map = {s.id: s for s in snapshots}
            stale = []
            for row in previous:
                if row.state in ("assigned", "scored"):
                    snapshot = snapshot_map.get(row.submission_snapshot_id)
                    judge = runtime().judge(row.judge_role_assignment_id)
                    if not snapshot or not eligible(judge, snapshot, round):
                        stale.append(row)
            if round.mode == "top3":
                affected = {(r.judge_role_assignment_id, r.batch) for r in stale}
                stale = [r for r in previous if r in stale or (r.state == "scored"
                         and (r.judge_role_assignment_id, r.batch) in affected)]
            stale_ids = {row.pk for row in stale}
            for row in previous:
                pair = (row.submission_snapshot_id, row.judge_role_assignment_id)
                if pair[0] in ids and pair[1] in valid_judges:
                    if row.state in ("assigned", "scored") and row.pk not in stale_ids and pair not in blocked:
                        existing.add(pair)
                    else:
                        blocked.add(pair)
            # Existing work by judges not selected is included in coverage via separate deficit targets below.
            # Require the full live pool on reassign so workload and coverage are not understated.
            live_prior = {r.judge_role_assignment_id for r in previous if r.state in ("assigned", "scored") and r.pk not in stale_ids}
            if live_prior - valid_judges:
                invalid("Include the existing judge pool when rebalancing this round.")
            try:
                plan = plan_assignments(ids, valid_judges, target_views=round.min_reviews, blocked=blocked,
                                        existing=existing, max_load=values["max_load"], seed=values["seed"])
            except ValueError as exc:
                raise ProgrammeError("assignment_limits_exceeded", "The assignment request exceeds the supported limits.", status=413) from exc
            result = {"pairs": [{"snapshot_id": p, "judge_role_assignment_id": j} for p, j in plan.pairs],
                      "deficits": {str(k): v for k, v in plan.deficits.items()},
                      "loads": {str(k): v for k, v in plan.loads.items()}, "coverage_complete": not plan.deficits}
            if not values["dry_run"]:
                if plan.deficits:
                    raise ProgrammeError("insufficient_judges", "Add nonconflicted judges or increase their workload limit.")
                for row in stale:
                    row.state = "invalidated"
                    changed(event, actor, "assignment_invalidated", row)
                    notice(event, "assignment_invalidated", row.pk, row.version)
                for snapshot, judge in plan.pairs:
                    project = snapshot_map[snapshot]
                    person = next(j for j in judges if j.role_assignment_id == judge)
                    possible_tracks = set(project.track_ids) & set(person.track_ids) if person.track_ids else set(project.track_ids)
                    assignment = JudgeAssignment.objects.create(event=event, round=round, judge_role_assignment_id=judge,
                                                   submission_snapshot_id=snapshot,
                                                   track_id=min(possible_tracks) if possible_tracks else None,
                                                   batch=f"v{round.version + 1}", room=project.room)
                    notice(event, "judge_assigned", assignment.pk, assignment.version)
                changed(event, actor, "judges_assigned", round, count=len(plan.pairs))
            return {**envelope(round), **result}
        return command(event, actor, values, path=f"judging-rounds/{round_id}/assign", run=run)
