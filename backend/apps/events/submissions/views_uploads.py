from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .views_base import PrivateSubmissionView

from .api_assets import create_upload, operation_key, owned_asset, project_asset, resume_upload
from .asset_workflow import asset_command
from .models_assets import HackathonParticipantAsset
from .ports import boundary
from .resume_copy import copy_from_saved
from .serializers import (UploadSerializer, ResumeUploadSerializer, AssetResponseSerializer,
                          AssetCommandSerializer, PartsSerializer, FromSavedSerializer, CommandSerializer,
                          UploadResponseSerializer, AssetCommandResponseSerializer, PartsResponseSerializer,
                          UploadDescriptorSerializer, ResumePageSerializer)
from .views_projects import ERRORS

KEY = [OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)]


class UploadView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]
    participant = False

    @extend_schema(request=UploadSerializer, parameters=KEY, responses={201: UploadResponseSerializer, **ERRORS}, tags=["Event uploads"])
    def post(self, request, pk, team_id=None, **kwargs):
        cls = ResumeUploadSerializer if self.participant else UploadSerializer
        serializer = cls(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(create_upload(actor=request.user, event_id=pk, team_id=team_id,
            participant=self.participant, operation_id=operation_key(request), data=serializer.validated_data), status=201)


class ResumeCollectionView(UploadView):
    participant = True

    @extend_schema(responses={200: ResumePageSerializer, **ERRORS}, tags=["Event resumes"])
    def get(self, request, pk, **kwargs):
        with boundary().locked(actor=request.user, event_id=pk, team_id=None, action="participant_read"):
            rows = HackathonParticipantAsset.objects.filter(event_id=pk, member=request.user).order_by("-pk")
            paginator = PageNumberPagination()
            paginator.page_size = 24
            page = paginator.paginate_queryset(rows, request)
            return paginator.get_paginated_response([project_asset(asset) for asset in page])

    @extend_schema(request=ResumeUploadSerializer, parameters=KEY, responses={201: UploadResponseSerializer, **ERRORS}, tags=["Event resumes"])
    def post(self, request, pk, **kwargs):
        return super().post(request, pk, **kwargs)


class AssetDetailView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]
    participant = False

    @extend_schema(responses={200: AssetResponseSerializer, **ERRORS}, tags=["Event uploads"])
    def get(self, request, pk, asset_id, team_id=None, **kwargs):
        asset = owned_asset(actor=request.user, event_id=pk, team_id=team_id, asset_id=asset_id, participant=self.participant)
        return Response(project_asset(asset))


class ResumeDetailView(AssetDetailView):
    participant = True

    @extend_schema(request=CommandSerializer, responses={200: AssetCommandResponseSerializer, **ERRORS}, tags=["Event resumes"])
    def delete(self, request, pk, asset_id, **kwargs):
        serializer = CommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = owned_asset(actor=request.user, event_id=pk, team_id=None, asset_id=asset_id, participant=True)
        return Response(asset_command(actor=request.user, event_id=pk, team_id=None, asset_id=asset_id,
            participant=True, action="delete", generation=asset.generation, **serializer.validated_data))


class AssetCommandView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]
    participant = False
    action = "complete"

    @extend_schema(request=AssetCommandSerializer, responses={200: AssetCommandResponseSerializer, 202: AssetCommandResponseSerializer, **ERRORS}, tags=["Event uploads"])
    def post(self, request, pk, asset_id, team_id=None, **kwargs):
        cls = PartsSerializer if self.action == "parts" else AssetCommandSerializer
        serializer = cls(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if self.action in {"resume", "parts"}:
            return Response(resume_upload(actor=request.user, event_id=pk, team_id=team_id,
                asset_id=asset_id, participant=self.participant, **data))
        result = asset_command(actor=request.user, event_id=pk, team_id=team_id, asset_id=asset_id,
                               participant=self.participant, action=self.action, **data)
        if self.action == "complete":
            result["status_url"] = request.path.rsplit("complete/", 1)[0]
        return Response(result, status=202 if self.action == "complete" else 200)


class FromSavedView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=FromSavedSerializer, parameters=KEY, responses={202: AssetCommandResponseSerializer, **ERRORS}, tags=["Event resumes"])
    def post(self, request, pk, **kwargs):
        serializer = FromSavedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = copy_from_saved(actor=request.user, event_id=pk, operation_id=operation_key(request), **serializer.validated_data)
        result["status_url"] = request.path.rsplit("from-saved/", 1)[0] + f"{result['asset_id']}/"
        return Response(result, status=202)


class AssetPartsView(AssetCommandView):
    action = "parts"

    @extend_schema(request=PartsSerializer, responses={200: PartsResponseSerializer, **ERRORS}, tags=["Event uploads"])
    def post(self, request, pk, asset_id, team_id=None, **kwargs):
        return super().post(request, pk, asset_id, team_id, **kwargs)


class AssetResumeView(AssetCommandView):
    action = "resume"

    @extend_schema(request=AssetCommandSerializer, responses={200: UploadDescriptorSerializer, **ERRORS}, tags=["Event uploads"])
    def post(self, request, pk, asset_id, team_id=None, **kwargs):
        return super().post(request, pk, asset_id, team_id, **kwargs)
