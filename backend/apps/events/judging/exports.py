"""Parity E-B4 (D6): the judging scores CSV, one row per project per round.

Reads only the frozen round calculation and the scored assignments. It never touches a judge's notes,
the feedback written for a team or an email address; a judge's name is shown only to a reader who may
see personal data, and is otherwise a stable "Judge n".
"""

from django.http import Http404

from .models_definitions import JudgingRound
from .models_scoring import JudgeAssignment
from .ports import runtime
from .projections import round_calculation

BASE_COLUMNS = ("round", "mode", "rank", "project", "reviews", "raw_score", "adjusted_score", "score", "judges")


def _rounds(event, round_id):
    rounds = JudgingRound.objects.filter(event=event).exclude(state="draft").order_by("pk")
    if round_id is not None:
        rounds = rounds.filter(pk=round_id)
        if not rounds.exists():
            raise Http404
    return list(rounds)


def _criteria(rounds):
    """Criterion key -> label, in the order first met across the rounds."""
    found = {}
    for round in rounds:
        for criterion in (round.configuration or {}).get("criteria", []):
            found.setdefault(criterion["key"], criterion["label"])
    return found


def _judge_names(member_ids, *, names_visible):
    from apps.accounts.models import User
    shown = {}
    if names_visible:
        shown = {pk: name for pk, name in User.objects.filter(pk__in=member_ids).values_list("pk", "display_name")}
    return {pk: shown.get(pk) or f"Judge {index}" for index, pk in enumerate(sorted(member_ids), start=1)}


def scores_columns(event, round_id=None):
    labels = _criteria(_rounds(event, round_id))
    return [*BASE_COLUMNS[:-1], *(f"average {label}" for label in labels.values()), BASE_COLUMNS[-1]]


def scores_rows(event, *, round_id=None, names_visible=False):
    """Yield one dict per (round, project), best rank first. Columns match `scores_columns`."""
    rounds = _rounds(event, round_id)
    labels = _criteria(rounds)
    for round in rounds:
        calculation = round_calculation(round)
        scored = {}
        for assignment in JudgeAssignment.objects.filter(round=round, state="scored").order_by("pk"):
            judge = runtime().judge(assignment.judge_role_assignment_id)
            scored.setdefault(assignment.submission_snapshot_id, set()).add(judge.member_id)
        names = _judge_names({m for ids in scored.values() for m in ids}, names_visible=names_visible)
        for row in sorted(calculation["rows"], key=lambda r: (r["rank"], r["snapshot_id"])):
            averages = row.get("criterion_averages") or {}
            values = {"round": round.key, "mode": round.mode, "rank": row["rank"],
                      "project": runtime().snapshot(row["snapshot_id"]).title, "reviews": row["n"],
                      "raw_score": row.get("raw_score"), "adjusted_score": row.get("zscore"),
                      "score": row.get("score"),
                      "judges": "; ".join(sorted(names[m] for m in scored.get(row["snapshot_id"], ())))}
            for key, label in labels.items():
                values[f"average {label}"] = averages.get(key)
            yield values
