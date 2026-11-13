"""Staff routes for review stages: settings, panel, seeded assignment and per-stage progress."""
from statistics import mean

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from . import admission_stage_assign, admission_stages
from .admission_stage_models import AdmissionStage, AdmissionStageAssignment
from .api_base import AdminView, ProgrammeCommandThrottle
from .api_schema import ERRORS
from .review_projection import alias
from .serializers_stages import (
    ApplyInput, ApplyResultSerializer, PanelInput, PlanSerializer, StageAssignmentPreviewInput, ProgressRowSerializer,
    StageCreateInput, StageSerializer, StageUpdateInput,
)

TAGS = ["Event programme review stages"]


def project(stage):
    panel = stage.panel.filter(removed_at__isnull=True).select_related("reviewer")
    return {"id": stage.pk, "event_id": stage.event_id, "position": stage.position, "name": stage.name,
            "state": stage.state, "version": stage.version, "reviews_per_application": stage.reviews_per_application,
            "blind": stage.blind, "criteria": stage.criteria, "guidance": stage.guidance, "opens_at": stage.opens_at,
            "closes_at": stage.closes_at, "assignment_strategy": stage.assignment_strategy,
            "assignment_seed": stage.assignment_seed, "assigned_at": stage.assigned_at,
            "frozen": stage.frozen_at is not None,
            "panel": [{"reviewer_id": row.reviewer_id, "label": row.reviewer.display_name or row.reviewer.username}
                      for row in panel.order_by("reviewer_id")],
            "standing": len(admission_stage_assign.candidates(stage))}


class StageView(AdminView):
    permission = "review_applications"
    throttle_classes = [ProgrammeCommandThrottle]

    def stage_target(self, request, pk, stage_id=None):
        event, config = self.admin_target(request, pk)
        admission_stages.require_feature(event)
        stage = get_object_or_404(AdmissionStage, pk=stage_id, event=event) if stage_id else None
        return event, stage


class StageListView(StageView):
    @extend_schema(tags=TAGS, request=None, responses={200: StageSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        event, _ = self.stage_target(request, pk)
        return Response([project(stage) for stage in admission_stages.stages_for(event.pk)])

    @extend_schema(tags=TAGS, request=StageCreateInput, responses={201: StageSerializer, **ERRORS})
    def post(self, request, pk):
        self.stage_target(request, pk)
        stage = admission_stages.create(event_id=pk, actor=request.user, data=self.command_data(request, StageCreateInput))
        return Response(project(stage), status=201)


class StageDetailView(StageView):
    @extend_schema(tags=TAGS, request=StageUpdateInput, responses={200: StageSerializer, **ERRORS})
    def patch(self, request, pk, stage_id):
        self.stage_target(request, pk, stage_id)
        stage = admission_stages.update(event_id=pk, stage_id=stage_id, actor=request.user,
                                        data=self.command_data(request, StageUpdateInput))
        return Response(project(stage))


class StagePanelView(StageView):
    @extend_schema(tags=TAGS, request=PanelInput, responses={200: StageSerializer, **ERRORS})
    def put(self, request, pk, stage_id):
        self.stage_target(request, pk, stage_id)
        stage = admission_stages.set_panel(event_id=pk, stage_id=stage_id, actor=request.user,
                                           data=self.command_data(request, PanelInput))
        return Response(project(stage))


class StagePreviewView(StageView):
    @extend_schema(tags=TAGS, request=StageAssignmentPreviewInput, responses={200: PlanSerializer, **ERRORS},
                   summary="Preview a seeded reviewer assignment; nothing is written")
    def post(self, request, pk, stage_id):
        event, stage = self.stage_target(request, pk, stage_id)
        data = StageAssignmentPreviewInput(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(admission_stage_assign.preview(event=event, stage=stage, **data.validated_data))


class StageApplyView(StageView):
    @extend_schema(tags=TAGS, request=ApplyInput, responses={200: ApplyResultSerializer, **ERRORS},
                   summary="Apply the previewed assignment when its fingerprint still matches")
    def post(self, request, pk, stage_id):
        self.stage_target(request, pk, stage_id)
        stage, created = admission_stage_assign.apply(event_id=pk, stage_id=stage_id, actor=request.user,
                                                      data=self.command_data(request, ApplyInput))
        return Response({"stage": project(stage), "created": created})


class StageProgressView(StageView):
    @extend_schema(tags=TAGS, request=None, responses={200: ProgressRowSerializer(many=True), **ERRORS},
                   summary="Per-application review coverage and average score in one stage")
    def get(self, request, pk, stage_id):
        from .admission_stage_review import coverage
        _, stage = self.stage_target(request, pk, stage_id)
        rows = []
        for application in admission_stage_assign.candidates(stage):
            scores = [sum(r.review.scores.values()) / max(len(r.review.scores), 1) for r in
                      AdmissionStageAssignment.objects.filter(stage=stage, application=application, state="submitted")
                      .select_related("review")]
            rows.append({"application_id": application.pk, "alias": alias(application.event_id, application.pk),
                         "state": application.state, "version": application.version,
                         "reviews": coverage(stage, application), "needed": stage.reviews_per_application,
                         "average": round(mean(scores), 2) if scores else None})
        return Response(rows)
