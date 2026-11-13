"""Pairwise HTTP adapters. Judges read only their own cursor; standings are organiser-only."""

from django.http import Http404
from drf_spectacular.utils import extend_schema_view
from rest_framework.response import Response

from .api_common import PrivateView, admin_event, paginated, schema
from .models_definitions import JudgingRound
from .models_pairwise import JudgePairwiseComparison, JudgePairwiseCursor
from .pairwise_projection import card, live_snapshots, require_pairwise, standings
from .pairwise_workflow import actor_judge, candidates, compare, live, next_project, recuse_current, skip_current
from .serializers import CommandInput, ReasonInput
from .serializers_pairwise import CompareInput, PairwiseCommandResult, PairwiseStandingsRead, PairwiseStateRead, SkipInput

GUIDANCE = "Choose the project that better meets the event's judging brief."


def judge_view(actor, round, event):
    round.event = event
    judge = actor_judge(actor, event.pk)
    cursor = JudgePairwiseCursor.objects.filter(round=round, judge_id=judge.role_assignment_id).first()
    previous = live(cursor.previous, actor, round, "scored") if cursor else None
    current = live(cursor.current, actor, round, "assigned") if cursor else None
    remaining = len(candidates(round, judge, live_snapshots(round))) if round.state == "open" else 0
    actions = []
    if round.state == "open":
        if current is not None:
            actions = (["compare"] if previous else ["next"]) + ["skip", "recuse"]
        elif remaining:
            actions = ["next"]
    compared = JudgePairwiseComparison.objects.filter(round=round, judge_id=judge.role_assignment_id).exclude(outcome="skip").count()
    return {"round_id": round.pk, "round_key": round.key, "event_id": event.pk, "version": cursor.version if cursor else 0,
            "guidance": round.configuration.get("guidance") or GUIDANCE,
            "previous": card(previous) if previous else None, "current": card(current) if current else None,
            "compared": compared, "remaining": remaining, "finished": current is None and not remaining,
            "allowed_actions": actions}


def _round(event, round_id):
    require_pairwise(event)
    round = JudgingRound.objects.filter(event=event, pk=round_id, mode="pairwise").first()
    if round is None:
        raise Http404
    return round


class PairwiseRounds(PrivateView):
    @schema(response=PairwiseStateRead(many=True), page=True,
            description="Open pairwise rounds for the signed-in judge, each with their own cursor state.")
    def get(self, request, pk):
        event = admin_event(request, pk, "judge")
        require_pairwise(event)
        rows = JudgingRound.objects.filter(event=event, mode="pairwise", state="open").order_by("pk")
        return paginated(request, [judge_view(request.user, row, event) for row in rows], PairwiseStateRead)


class PairwiseState(PrivateView):
    @schema(response=PairwiseStateRead, description="The judge's own cursor: the project before, the one now, and progress.")
    def get(self, request, pk, round_id):
        event = admin_event(request, pk, "judge")
        return Response(PairwiseStateRead(judge_view(request.user, _round(event, round_id), event)).data)


class PairwiseCommand(PrivateView):
    handler = staticmethod(next_project)

    def post(self, request, pk, round_id):
        return Response(self.handler(pk, round_id, actor=request.user, data=request.data))


@extend_schema_view(post=schema(request=CommandInput, response=PairwiseCommandResult,
                                description="Show the next project (after the first view, or after a skip or recusal)."))
class PairwiseNext(PairwiseCommand):
    pass


@extend_schema_view(post=schema(request=CompareInput, response=PairwiseCommandResult,
                                description="Record which project was better: the one before or this one."))
class PairwiseCompare(PairwiseCommand):
    handler = staticmethod(compare)


@extend_schema_view(post=schema(request=SkipInput, response=PairwiseCommandResult,
                                description="Can't judge this one: the current project is skipped and never compared."))
class PairwiseSkip(PairwiseCommand):
    handler = staticmethod(skip_current)


@extend_schema_view(post=schema(request=ReasonInput, response=PairwiseCommandResult,
                                description="Declare a conflict with the current project through the existing recusal workflow."))
class PairwiseRecuse(PairwiseCommand):
    handler = staticmethod(recuse_current)


class PairwiseStandings(PrivateView):
    @schema(response=PairwiseStandingsRead,
            description="Live CrowdBT standings and per-judge coverage for organisers. Never shown to judges; results publish only through results finalize/publish.")
    def get(self, request, pk, round_id):
        event = admin_event(request, pk)
        return Response(PairwiseStandingsRead(standings(_round(event, round_id))).data)
