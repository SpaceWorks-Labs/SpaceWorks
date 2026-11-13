"""Superadmin API for offsite backup destinations. Deployment-level; never module-gated.

Decision 220(e), widened by owner rule 261: every WRITE route (create, any update, retire,
probe, push now, rehydrate) needs a recent server-owned re-authentication -- the same
`require_recent_reauth` (403 `recent_reauth_required`) staff role grants and payment
credentials use. Reads do not.
"""

from django.utils.translation import gettext
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication import require_recent_reauth
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.backup.models import BackupArchive, BackupDestination, BackupDestinationUpload
from apps.backup.offsite_restore import validate_rehydration
from apps.backup.serializers_offsite import (
    BackupDestinationSerializer,
    BackupDestinationUploadSerializer,
    BackupDestinationPageSerializer,
    BackupDestinationUploadPageSerializer,
    DestinationDispatchSerializer,
    DestinationProbeSerializer,
    RehydrateSerializer,
    audit_meta,
)
from apps.backup.services_offsite import probe_destination, retire_destination
from apps.backup.tasks_offsite import dispatch_offsite_push, rehydrate_backup_archive_task
from apps.backup.views_common import AUTH_ERRORS, NOT_FOUND, VALIDATION_ERROR

TAGS = ["Backup destinations"]
PAGE = [OpenApiParameter("page", int, description="Page number (24 rows per page).")]
REAUTH_ERRORS = {**AUTH_ERRORS, 403: OpenApiResponse(
    description="Not authorized, or `recent_reauth_required`: re-authenticate (ten-minute window) and retry.")}


def _page(rows, request, serializer):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(rows, request)
    return paginator.get_paginated_response(serializer(page, many=True).data)


class BackupDestinationListCreateView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="List offsite backup destinations", parameters=PAGE, responses={200: BackupDestinationPageSerializer, 404: NOT_FOUND, **AUTH_ERRORS})
    def get(self, request):
        rows = BackupDestination.objects.all()
        return _page(rows, request, BackupDestinationSerializer)

    @extend_schema(tags=TAGS, summary="Register an S3-compatible offsite backup destination", description="Adding a push target needs a recent re-authentication (ten-minute window).", request=BackupDestinationSerializer, responses={201: BackupDestinationSerializer, 400: VALIDATION_ERROR, **REAUTH_ERRORS})
    def post(self, request):
        require_recent_reauth(request)
        serializer = BackupDestinationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            destination = serializer.save(created_by=request.user)
            audit.record(
                request.user, "backup.destination_created", target=destination,
                meta=audit_meta(serializer.validated_data),
            )
        return Response(BackupDestinationSerializer(destination).data, status=status.HTTP_201_CREATED)


class BackupDestinationDetailView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Get one offsite backup destination", responses={200: BackupDestinationSerializer, 404: NOT_FOUND, **AUTH_ERRORS})
    def get(self, request, destination_id):
        return Response(BackupDestinationSerializer(get_object_or_404(BackupDestination, pk=destination_id)).data)

    @extend_schema(tags=TAGS, summary="Update or rotate credentials of an offsite destination", description="Every update (credentials, re-pointing, `enabled`, `name`, `retention_days`) needs a recent re-authentication (ten-minute window).", request=BackupDestinationSerializer, responses={200: BackupDestinationSerializer, 400: VALIDATION_ERROR, 404: NOT_FOUND, **REAUTH_ERRORS})
    def patch(self, request, destination_id):
        require_recent_reauth(request)
        with transaction.atomic():
            destination = get_object_or_404(
                BackupDestination.objects.select_for_update(), pk=destination_id
            )
            serializer = BackupDestinationSerializer(destination, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            destination = serializer.save()
            audit.record(
                request.user, "backup.destination_updated", target=destination,
                meta=audit_meta(serializer.validated_data),
            )
        return Response(BackupDestinationSerializer(destination).data)


class BackupDestinationRetireView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Retire a destination: stop pushing and wipe its stored credentials", request=None, responses={200: BackupDestinationSerializer, 400: VALIDATION_ERROR, 404: NOT_FOUND, **REAUTH_ERRORS})
    def post(self, request, destination_id):
        require_recent_reauth(request)
        get_object_or_404(BackupDestination, pk=destination_id)
        destination = retire_destination(destination_id, request.user)
        return Response(BackupDestinationSerializer(destination).data)


class BackupDestinationProbeView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Probe write, read-back and delete on a destination", description="Uses the stored credentials against the remote bucket, so it needs a recent re-authentication (ten-minute window).", request=None, responses={200: DestinationProbeSerializer, 404: NOT_FOUND, **REAUTH_ERRORS})
    def post(self, request, destination_id):
        require_recent_reauth(request)
        destination = get_object_or_404(
            BackupDestination, pk=destination_id, retired_at__isnull=True
        )
        return Response(probe_destination(destination, request.user))


class BackupDestinationUploadListView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="List the upload journal of one destination", parameters=PAGE, responses={200: BackupDestinationUploadPageSerializer, 404: NOT_FOUND, **AUTH_ERRORS})
    def get(self, request, destination_id):
        destination = get_object_or_404(BackupDestination, pk=destination_id)
        rows = BackupDestinationUpload.objects.filter(destination=destination).select_related("destination").order_by("-created_at", "-pk")
        return _page(rows, request, BackupDestinationUploadSerializer)


class BackupDestinationPushView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Start an offsite push now instead of waiting for the schedule", request=None, responses={202: DestinationDispatchSerializer, 503: OpenApiResponse(description="The backup worker is unavailable."), **REAUTH_ERRORS})
    def post(self, request):
        require_recent_reauth(request)
        audit.record(request.user, "backup.offsite_push_requested", target=None, meta={})
        if not dispatch_offsite_push():
            return Response({"detail": gettext("The backup worker is unavailable.")}, status=503)
        return Response({"detail": gettext("Offsite push dispatched.")}, status=status.HTTP_202_ACCEPTED)


class BackupArchiveRehydrateView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Restore an archive's primary bytes from a verified offsite copy", request=RehydrateSerializer, responses={202: DestinationDispatchSerializer, 400: VALIDATION_ERROR, 404: NOT_FOUND, 503: OpenApiResponse(description="The backup worker is unavailable."), **REAUTH_ERRORS})
    def post(self, request, archive_id):
        require_recent_reauth(request)
        archive = get_object_or_404(BackupArchive, pk=archive_id)
        serializer = RehydrateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        destination = serializer.validated_data["destination"]
        validate_rehydration(archive, destination)
        from apps.operations.durable_dispatch import resident_delivery

        if not resident_delivery():
            # No durable rehydration request model exists. Never report queued
            # work which cannot survive this request or execute it eagerly here.
            return Response({"detail": gettext("The backup worker is unavailable.")}, status=503)
        audit.record(
            request.user, "backup.archive_rehydrate_requested", target=archive,
            meta={"destination_id": destination.pk},
        )
        try:
            rehydrate_backup_archive_task.delay(str(archive.pk), destination.pk, request.user.pk)
        except Exception:
            return Response({"detail": gettext("The backup worker is unavailable.")}, status=503)
        return Response({"detail": gettext("Rehydration dispatched.")}, status=status.HTTP_202_ACCEPTED)
