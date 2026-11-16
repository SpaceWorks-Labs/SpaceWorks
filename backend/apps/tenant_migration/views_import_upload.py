"""Superadmin-only resumable tenant-archive upload endpoints."""

import re

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response

from .import_chunk_parser import OffsetChunkParser
from .serializers import ImportJobSerializer, TypedErrorSerializer
from .serializers_import_upload import (
    ImportUploadConflictSerializer, ImportUploadStartSerializer,
)
from .services_import_upload import (
    complete_import_upload, receive_import_chunk, start_import_upload,
)
from .views_admission_export import MigrationAPIView
from .views_common import AUTH_ERRORS, CONFLICT, FIELD_ERRORS, NOT_FOUND, protocol_error
from .views_import import _job


class TenantImportUploadStartView(MigrationAPIView):
    @extend_schema(
        tags=["Tenant migration"], summary="Start a resumable encrypted archive upload",
        request=ImportUploadStartSerializer,
        responses={201: ImportJobSerializer, 400: FIELD_ERRORS, **AUTH_ERRORS},
    )
    def post(self, request):
        serializer = ImportUploadStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = start_import_upload(actor=request.user, **serializer.validated_data)
        except Exception as exc:
            return protocol_error(exc)
        return Response(ImportJobSerializer(job).data, status=201)


class TenantImportArchiveChunkView(MigrationAPIView):
    parser_classes = [OffsetChunkParser]

    def get_throttles(self):
        # MigrationAPIView.get_throttles would replace this with its write scope.
        self.throttle_scope = "tenant_migration_upload"
        return [throttle() for throttle in self.throttle_classes]

    @extend_schema(
        tags=["Tenant migration"], summary="Append up to 8 MiB at the current upload offset",
        request={OffsetChunkParser.media_type: OpenApiTypes.BINARY},
        parameters=[
            OpenApiParameter(
                "Upload-Offset", OpenApiTypes.INT, OpenApiParameter.HEADER,
                required=True, description="Nonnegative byte offset; must equal upload_received_bytes.",
            ),
            OpenApiParameter(
                "Content-Length", OpenApiTypes.INT, OpenApiParameter.HEADER,
                required=True, description="Chunk length in bytes, from 1 through 8388608.",
            ),
        ],
        responses={
            200: ImportJobSerializer,
            400: OpenApiResponse(TypedErrorSerializer, description="Invalid length, offset or size overflow."),
            404: NOT_FOUND,
            409: OpenApiResponse(ImportUploadConflictSerializer, description="State conflict or offset_mismatch with upload_received_bytes."),
            415: OpenApiResponse(TypedErrorSerializer, description="Requires application/offset+octet-stream."),
            **AUTH_ERRORS,
        },
    )
    def patch(self, request, job_id):
        _job(request.user, job_id)
        # Force the one bounded parse before entering the service's transaction.
        chunk = request.data
        try:
            offset = request.headers.get("Upload-Offset", "")
            if not re.fullmatch(r"[0-9]{1,20}", offset):
                raise ValueError("Upload-Offset must be a nonnegative integer.")
            job = receive_import_chunk(
                actor=request.user, job_id=job_id, offset=int(offset), chunk=chunk,
            )
        except Exception as exc:
            return protocol_error(exc)
        return Response(ImportJobSerializer(job).data)


class TenantImportArchiveCompleteView(MigrationAPIView):
    @extend_schema(
        tags=["Tenant migration"], summary="Complete an archive upload and queue staging",
        request=None,
        responses={202: ImportJobSerializer, 404: NOT_FOUND, 409: CONFLICT, **AUTH_ERRORS},
    )
    def post(self, request, job_id):
        _job(request.user, job_id)
        try:
            job = complete_import_upload(actor=request.user, job_id=job_id)
        except Exception as exc:
            return protocol_error(exc)
        return Response(ImportJobSerializer(job).data, status=202)
