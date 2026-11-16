"""Stage file routes use the owner and selected-answer byte gateway."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework.response import Response
from .http import PrivateView, body, member_event
from .serializers import StageCommand, ERRORS
from .serializers_uploads import (StageFileCreateCommand, StageFileCompleteCommand,
    StageFileSerializer, StageFileCreatedSerializer, StageFileCommandResult)
from .upload_models import StageFormAsset
from .upload_commands import project
from . import upload_workflow, upload_reads

KEY = [OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)]


class StageFileCreateView(PrivateView):
    @extend_schema(tags=["Event stage files"], parameters=KEY, request=StageFileCreateCommand,
                   responses={201: StageFileCreatedSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk, stage_form_id):
        member_event(request, pk, makerspace_id)
        return Response(upload_workflow.create(event_id=pk, stage_form_id=stage_form_id,
            actor=request.user, data=body(request, StageFileCreateCommand)), status=201)


class StageFileDetailView(PrivateView):
    @extend_schema(tags=["Event stage files"], responses={200: StageFileSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk, stage_form_id, asset_id):
        event = member_event(request, pk, makerspace_id)
        row = get_object_or_404(StageFormAsset, pk=asset_id, event=event, owner_member=request.user,
                               assignment__stage_form_id=stage_form_id)
        return Response(project(row))

    @extend_schema(tags=["Event stage files"], parameters=KEY, request=StageCommand,
                   responses={200: StageFileCommandResult, **ERRORS})
    def delete(self, request, makerspace_id, pk, stage_form_id, asset_id):
        member_event(request, pk, makerspace_id)
        return Response(upload_workflow.delete(event_id=pk, stage_form_id=stage_form_id, asset_id=asset_id,
            actor=request.user, data=body(request, StageCommand)))


class StageFileCompleteView(PrivateView):
    @extend_schema(tags=["Event stage files"], parameters=KEY, request=StageFileCompleteCommand,
                   responses={202: StageFileCommandResult, **ERRORS})
    def post(self, request, makerspace_id, pk, stage_form_id, asset_id):
        member_event(request, pk, makerspace_id)
        return Response(upload_workflow.complete(event_id=pk, stage_form_id=stage_form_id, asset_id=asset_id,
            actor=request.user, data=body(request, StageFileCompleteCommand)), status=202)


class StageFileDownloadView(PrivateView):
    @extend_schema(tags=["Event stage files"], parameters=[OpenApiParameter("Range", str, OpenApiParameter.HEADER)],
                   responses={200: OpenApiTypes.BINARY, 206: OpenApiTypes.BINARY, 416: None, **ERRORS})
    def get(self, request, makerspace_id, pk, stage_form_id, asset_id):
        return upload_reads.download(request, event_id=pk, makerspace_id=makerspace_id, stage_form_id=stage_form_id, asset_id=asset_id)


class StageStaffFileDownloadView(PrivateView):
    @extend_schema(tags=["Event stage files"], parameters=[OpenApiParameter("response_revision", int, required=True),
        OpenApiParameter("Range", str, OpenApiParameter.HEADER)],
        responses={200: OpenApiTypes.BINARY, 206: OpenApiTypes.BINARY, 416: None, **ERRORS})
    def get(self, request, pk, asset_id):
        return upload_reads.download(request, event_id=pk, asset_id=asset_id, staff=True)
