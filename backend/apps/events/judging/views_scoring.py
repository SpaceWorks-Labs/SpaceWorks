"""A judge sees only their own live eligible assignments and private notes."""

from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema_view
from rest_framework.response import Response

from .api_common import PrivateView, admin_event, paginated, schema
from .boundary import envelope
from .conflicts import require_assignment
from .models_scoring import JudgeAssignment, JudgeScore
from .ports import runtime
from .scoring_workflow import rank, recuse_or_skip, score
from .serializers import RankInput, ReasonInput, ResultEnvelope, ScoreInput
from .serializers_read import AssignmentRead


def assignment_projection(actor, row, event):
    round = row.round
    round.event = event
    _, snapshot = require_assignment(actor, row, round)
    own_score = JudgeScore.objects.filter(assignment=row).first()
    batch_projects = []
    for peer in round.assignments.filter(judge_role_assignment_id=row.judge_role_assignment_id, batch=row.batch,
                                         state="assigned").order_by("pk"):
        try:
            _, project = require_assignment(actor, peer, round)
        except Http404:
            continue
        batch_projects.append({"snapshot_id": project.id, "title": project.title})
    can_score = round.state == "open" and row.state == "assigned" and (not round.closes_at or timezone.now() < round.closes_at)
    can_recuse = round.state == "open" and row.state in ("assigned", "scored") and (not round.closes_at or timezone.now() < round.closes_at)
    return envelope(row, round_id=round.pk, snapshot_id=snapshot.id, title=snapshot.title,
        description=snapshot.description, mode=round.mode, batch=row.batch, configuration=round.configuration,
        scores=own_score.criterion_values if own_score else {}, notes=own_score.notes if own_score else "",
        asset_ids=list(snapshot.judge_asset_ids), batch_projects=batch_projects,
        allowed_actions=(["score" if round.mode == "weighted_1_5" else "rank"] if can_score else [])
        + (["recuse", "skip"] if can_recuse else []))


class AssignmentList(PrivateView):
    @schema(response=AssignmentRead(many=True), page=True)
    def get(self, request, pk):
        event = admin_event(request, pk, "judge")
        roles = [j.role_assignment_id for j in runtime().judges(pk) if j.member_id == request.user.pk and j.active]
        rows = JudgeAssignment.objects.filter(event=event, judge_role_assignment_id__in=roles).select_related("round").order_by("pk")
        result = []
        for row in rows:
            try:
                result.append(assignment_projection(request.user, row, event))
            except Http404:
                continue
        return paginated(request, result, AssignmentRead)


class AssignmentDetail(PrivateView):
    @schema(response=AssignmentRead)
    def get(self, request, pk, assignment_id):
        event = admin_event(request, pk, "judge")
        row = JudgeAssignment.objects.filter(event=event, pk=assignment_id).select_related("round").first()
        if row is None:
            raise Http404
        return Response(AssignmentRead(assignment_projection(request.user, row, event)).data)


class AssignmentScore(PrivateView):
    @schema(request=ScoreInput, response=ResultEnvelope)
    def post(self, request, pk, assignment_id):
        return Response(score(pk, assignment_id, actor=request.user, data=request.data))


class AssignmentRank(PrivateView):
    @schema(request=RankInput, response=ResultEnvelope)
    def post(self, request, pk, assignment_id):
        return Response(rank(pk, assignment_id, actor=request.user, data=request.data))


class AssignmentReason(PrivateView):
    action = "recuse"

    def post(self, request, pk, assignment_id):
        return Response(recuse_or_skip(pk, assignment_id, actor=request.user, action=self.action, data=request.data))


@extend_schema_view(post=schema(request=ReasonInput, response=ResultEnvelope))
class AssignmentRecuse(AssignmentReason):
    pass


@extend_schema_view(post=schema(request=ReasonInput, response=ResultEnvelope))
class AssignmentSkip(AssignmentReason):
    action = "skip"
