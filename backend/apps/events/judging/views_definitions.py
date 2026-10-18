"""Definition/round HTTP adapters; all writes delegate to the owning workflow."""

from django.http import Http404
from drf_spectacular.utils import extend_schema_view
from rest_framework.response import Response

from .api_common import PrivateView, admin_event, paginated, schema
from .definitions_workflow import save_definition
from .models_definitions import HackathonPrize, HackathonTrack, JudgingRound
from .projections import progress
from .round_workflow import assign, transition
from .serializers import AssignInput, CommandInput, FinalizeRoundInput, PrizeInput, ResultEnvelope, RoundInput, TrackInput
from .serializers_read import AssignmentPlanRead, PrizeRead, RoundRead, TrackRead


class DefinitionList(PrivateView):
    kind = "tracks"
    model = HackathonTrack
    output = TrackRead

    def get(self, request, pk):
        event = admin_event(request, pk)
        rows = self.model.objects.filter(event=event).order_by("pk")
        if self.model is JudgingRound:
            return paginated(request, [progress(row, actor=request.user) for row in rows], RoundRead)
        return paginated(request, rows, self.output)

    def post(self, request, pk):
        result = save_definition(pk, actor=request.user, kind=self.kind, data=request.data)
        return Response(result, status=201)


class DefinitionDetail(DefinitionList):
    id_kwarg = "track_id"

    def get(self, request, pk, **kwargs):
        event = admin_event(request, pk)
        row = self.model.objects.filter(event=event, pk=kwargs[self.id_kwarg]).first()
        if not row:
            raise Http404
        return Response(RoundRead(progress(row, actor=request.user)).data if self.model is JudgingRound else self.output(row).data)

    def patch(self, request, pk, **kwargs):
        return Response(save_definition(pk, actor=request.user, kind=self.kind,
            data=request.data, object_id=kwargs[self.id_kwarg]))

    http_method_names = ["get", "patch", "head", "options"]


@extend_schema_view(get=schema(response=TrackRead(many=True), page=True),
                    post=schema(request=TrackInput, response=ResultEnvelope, status=201))
class TrackList(DefinitionList):
    pass


@extend_schema_view(get=schema(response=TrackRead), patch=schema(request=TrackInput, response=ResultEnvelope))
class TrackDetail(DefinitionDetail):
    pass


@extend_schema_view(get=schema(response=PrizeRead(many=True), page=True),
                    post=schema(request=PrizeInput, response=ResultEnvelope, status=201))
class PrizeList(DefinitionList):
    kind, model, output = "prizes", HackathonPrize, PrizeRead


@extend_schema_view(get=schema(response=PrizeRead), patch=schema(request=PrizeInput, response=ResultEnvelope))
class PrizeDetail(DefinitionDetail):
    kind, model, output, id_kwarg = "prizes", HackathonPrize, PrizeRead, "prize_id"


@extend_schema_view(get=schema(response=RoundRead(many=True), page=True),
                    post=schema(request=RoundInput, response=ResultEnvelope, status=201))
class RoundList(DefinitionList):
    kind, model, output = "judging-rounds", JudgingRound, RoundRead


@extend_schema_view(get=schema(response=RoundRead), patch=schema(request=RoundInput, response=ResultEnvelope))
class RoundDetail(DefinitionDetail):
    kind, model, output, id_kwarg = "judging-rounds", JudgingRound, RoundRead, "round_id"


class RoundAction(PrivateView):
    action = "open"

    def post(self, request, pk, round_id):
        return Response(transition(pk, round_id, actor=request.user, action=self.action, data=request.data))


@extend_schema_view(post=schema(request=CommandInput, response=ResultEnvelope))
class RoundOpen(RoundAction):
    pass


@extend_schema_view(post=schema(request=CommandInput, response=ResultEnvelope))
class RoundClose(RoundAction):
    action = "close"


@extend_schema_view(post=schema(request=FinalizeRoundInput, response=ResultEnvelope))
class RoundFinalize(RoundAction):
    action = "finalize"


class RoundAssign(PrivateView):
    @schema(request=AssignInput, response=AssignmentPlanRead,
            description="Balanced deterministic plan; dry_run returns pairs, deficits and loads without assignment writes.")
    def post(self, request, pk, round_id):
        return Response(assign(pk, round_id, actor=request.user, data=request.data))
