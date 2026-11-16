"""The panel reviewer's workspace routes. Panel membership is checked on every read and write."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.admin_api.permissions import IsActiveStaff

from . import admission_stage_review
from .admission_stage_models import AdmissionStage
from .api_base import ProgrammeCommandThrottle, ProgrammeView
from .api_schema import ERRORS
from .serializers_stages import (
    ReviewerAssignmentSerializer, ReviewerStageSerializer, ReviewerWorkspaceSerializer, StageReviewInput,
)

TAGS = ["Event programme review stages"]


class ReviewerView(ProgrammeView):
    # Any active person may call; a non-member of the panel reads 404 like an unknown stage.
    permission_classes = [IsActiveStaff]

    def stage(self, pk, stage_id):
        return get_object_or_404(AdmissionStage.objects.select_related("event__makerspace"), pk=stage_id, event_id=pk)


class MyReviewStagesView(ReviewerView):
    @extend_schema(tags=TAGS, request=None, responses={200: ReviewerStageSerializer(many=True), **ERRORS},
                   summary="Open review stages whose panel I sit on")
    def get(self, request):
        return Response(admission_stage_review.my_stages(request.user))


class MyStageAssignmentsView(ReviewerView):
    @extend_schema(tags=TAGS, request=None, responses={200: ReviewerWorkspaceSerializer, **ERRORS},
                   summary="My assignments in one stage, identity hidden when the stage is blind")
    def get(self, request, pk, stage_id):
        stage = self.stage(pk, stage_id)
        assignments = admission_stage_review.assignments_for(request.user, stage)  # panel check first
        return Response({"stage": admission_stage_review.project_stage(stage), "assignments": assignments})


class MyStageReviewSubmitView(ReviewerView):
    throttle_classes = [ProgrammeCommandThrottle]

    @extend_schema(tags=TAGS, request=StageReviewInput, responses={200: ReviewerAssignmentSerializer, **ERRORS},
                   summary="Submit my scores for one assignment, or recuse")
    def post(self, request, pk, stage_id, assignment_id):
        self.stage(pk, stage_id)
        data = StageReviewInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = admission_stage_review.submit(actor=request.user, stage_id=stage_id, assignment_id=assignment_id,
                                            data=data.validated_data)
        return Response(admission_stage_review.project_assignment(row))
