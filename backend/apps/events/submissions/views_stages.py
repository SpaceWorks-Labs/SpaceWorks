"""Staff routes for submission stages: the editor, shortlists, extensions and bulk triage (#177-#180).

Every route needs the hackathon manager for the event (publishing a shortlist needs the full event
manager, as publishing finalists does). Participants read the stages through the project payload.
"""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import stage_service, stage_shortlists, stage_staff
from .serializers import ErrorSerializer
from .serializers_stages import (BulkTriageInput, BulkTriageSerializer, ExtensionInput, ExtensionSerializer,
                                 ShortlistApplyInput, ShortlistPlanSerializer, ShortlistPreviewInput,
                                 ShortlistPromoteInput, ShortlistPublishInput, ShortlistSerializer, StagePlanInput, StagePlanSerializer)
from .views_base import PrivateSubmissionView

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 429, 503)}
TAGS = ["Event submissions"]


def _valid(serializer_class, request):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


class SubmissionStagesView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: StagePlanSerializer, **ERRORS}, tags=TAGS,
                   description="The event's submission stages, with the presets and choices the editor offers.")
    def get(self, request, pk):
        return Response(stage_service.read(actor=request.user, event_id=pk))

    @extend_schema(request=StagePlanInput, responses={200: StagePlanSerializer, **ERRORS}, tags=TAGS,
                   description="Replace the ordered stage list: add, edit, remove and reorder in one command. "
                               "A stage with submissions, a shortlist, an extension or a round cannot be removed "
                               "(stage_in_use); editing it never changes a frozen snapshot.")
    def put(self, request, pk):
        return Response(stage_service.replace(actor=request.user, event_id=pk, data=_valid(StagePlanInput, request)))


class StageShortlistView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ShortlistSerializer, **ERRORS}, tags=TAGS,
                   description="The stage's current shortlist and whether it is published (#179).")
    def get(self, request, pk, stage_id):
        return Response(stage_shortlists.read(actor=request.user, event_id=pk, stage_id=stage_id))


class StageShortlistPreviewView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShortlistPreviewInput, responses={200: ShortlistPlanSerializer, **ERRORS}, tags=TAGS,
                   description="Preview a shortlist (changes nothing). Refused with triage_pending while any of the "
                               "stage's submissions is untriaged.")
    def post(self, request, pk, stage_id):
        values = _valid(ShortlistPreviewInput, request)
        return Response(stage_shortlists.preview(actor=request.user, event_id=pk, stage_id=stage_id, values=values))


class StageShortlistApplyView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShortlistApplyInput, responses={200: ShortlistSerializer, **ERRORS}, tags=TAGS,
                   description="Apply the previewed shortlist (plan_changed if it moved). Closes the stage.")
    def post(self, request, pk, stage_id):
        values = _valid(ShortlistApplyInput, request)
        return Response(stage_shortlists.apply(actor=request.user, event_id=pk, stage_id=stage_id, values=values))


class StageShortlistPublishView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShortlistPublishInput, responses={200: ShortlistSerializer, **ERRORS}, tags=TAGS,
                   description="Publish the stage's current shortlist, once. It opens the next stage to the chosen "
                               "teams; both groups are emailed when the event's shortlist email is on.")
    def post(self, request, pk, stage_id):
        values = _valid(ShortlistPublishInput, request)
        return Response(stage_shortlists.publish(actor=request.user, event_id=pk, stage_id=stage_id, values=values))


class StageShortlistPromoteView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShortlistPromoteInput, responses={200: ShortlistSerializer, **ERRORS}, tags=TAGS,
                   description="S12: a shortlisted team withdrew before the next stage opened; promote the next "
                               "ranked team(s) from the shortlist's source round as a published amendment.")
    def post(self, request, pk, stage_id):
        from .stage_promotion import promote_next
        values = _valid(ShortlistPromoteInput, request)
        return Response(promote_next(actor=request.user, event_id=pk, stage_id=stage_id, values=values))


class StageExtensionView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ExtensionInput, responses={200: ExtensionSerializer, **ERRORS}, tags=TAGS,
                   description="Give one team a later deadline for this stage (S2). Late snapshots still say late.")
    def post(self, request, pk, stage_id):
        values = _valid(ExtensionInput, request)
        return Response(stage_staff.extend(actor=request.user, event_id=pk, stage_id=stage_id, values=values))


class StageTriageView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=BulkTriageInput, responses={200: BulkTriageSerializer, **ERRORS}, tags=TAGS,
                   description="Triage many of this stage's submissions at once (S5).")
    def post(self, request, pk, stage_id):
        values = _valid(BulkTriageInput, request)
        return Response(stage_staff.bulk_triage(actor=request.user, event_id=pk, stage_id=stage_id, values=values))
