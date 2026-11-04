"""Read/preview/finalize/release/correct result resources; GET never mutates."""

from drf_spectacular.utils import extend_schema_view
from rest_framework.response import Response

from . import results_workflow
from .api_common import PrivateView, admin_event, schema
from .models_definitions import JudgingRound
from .models_results import EventResultRevision, ResultPublicationState, SponsorWinnerProposal
from .serializers import PublishResultInput, ResultsInput, validated
from .serializers_read import PreviewInput, PreviewRead, ResultRead


class ResultsPreview(PrivateView):
    @schema(response=PreviewRead)
    def get(self, request, pk):
        event = admin_event(request, pk, None)
        ids = list(JudgingRound.objects.filter(event=event).values_list("pk", flat=True))
        return Response(results_workflow.preview(pk, actor=request.user, round_ids=ids))

    @schema(request=PreviewInput, response=PreviewRead)
    def post(self, request, pk):
        values = validated(PreviewInput, request.data)
        return Response(results_workflow.preview(pk, actor=request.user, round_ids=values["round_ids"]))


class ResultState(PrivateView):
    def get(self, request, pk):
        event = admin_event(request, pk, None)
        result = EventResultRevision.objects.filter(event=event).order_by("-version").first()
        return Response({"id": result.pk if result else 0, "event_id": pk, "version": result.version if result else 0,
            "state": "published" if result and ResultPublicationState.objects.filter(event=event,
                current_announcement__result=result).exists() else "finalized" if result else "draft",
            "allowed_actions": ["correct", "publish"] if result else ["finalize"],
            "aggregates": result.aggregates if result else {},
            "sponsor_proposals": list(SponsorWinnerProposal.objects.filter(event=event).order_by("pk")
                                       .values("id", "prize_id", "submission_snapshot_id", "created_at"))})


@extend_schema_view(get=schema(response=ResultRead))
class ResultsFinalize(ResultState):
    @schema(request=ResultsInput, response=ResultRead)
    def post(self, request, pk):
        return Response(results_workflow.finalize(pk, actor=request.user, data=request.data))


@extend_schema_view(get=schema(response=ResultRead))
class ResultsPublish(ResultState):
    @schema(request=PublishResultInput, response=ResultRead)
    def post(self, request, pk):
        return Response(results_workflow.publish(pk, actor=request.user, data=request.data))


@extend_schema_view(get=schema(response=ResultRead))
class ResultsCorrect(ResultState):
    @schema(request=ResultsInput, response=ResultRead)
    def post(self, request, pk):
        return Response(results_workflow.finalize(pk, actor=request.user, data=request.data, correction=True))
