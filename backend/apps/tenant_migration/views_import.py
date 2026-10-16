from datetime import timedelta
import logging

from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.admin_api.permissions import require_makerspace_superadmin_access
from apps.audit import services as audit
from apps.makerspaces.models import Makerspace

from .import_upload import ImportArchiveUploadHandler, PersistedImportUpload
from .import_visibility import scope_import_target_makerspaces
from .models_import_job import TenantImportJob
from .serializers import (
    ClosureIdentitySerializer,
    ImportCreateSerializer,
    ImportDecisionListSerializer,
    ImportJobSerializer,
    ImportRunSerializer,
    VerificationReportSerializer,
)
from .services_import_job import (
    claim_import_job,
    submit_identity_decisions,
)
from .services_import_staging import accept_import_upload, rows_archive_path
from .tasks import run_import_job_task, stage_import_job_task
from .views_admission_export import MigrationAPIView
from .views_common import AUTH_ERRORS, CONFLICT, FIELD_ERRORS, NOT_FOUND, protocol_error

logger = logging.getLogger(__name__)


def _job(actor, job_id):
    job = get_object_or_404(
        TenantImportJob.objects.select_related("target_makerspace"), pk=job_id
    )
    if job.target_makerspace is not None:
        require_makerspace_superadmin_access(actor, job.target_makerspace)
    return job


class TenantImportListCreateView(MigrationAPIView):
    def initialize_request(self, request, *args, **kwargs):
        if request.method == "POST":
            self.import_upload_handler = ImportArchiveUploadHandler(request)
            request.upload_handlers = [self.import_upload_handler]
        return super().initialize_request(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            handler = getattr(self, "import_upload_handler", None)
            if handler is not None:
                handler.cleanup()

    @extend_schema(tags=["Tenant migration"], summary="List tenant import jobs", responses={200: ImportJobSerializer(many=True), **AUTH_ERRORS})
    def get(self, request):
        visible_spaces = scope_import_target_makerspaces(
            request.user, Makerspace.objects.all()
        ).values_list("pk", flat=True)
        rows = TenantImportJob.objects.select_related("target_makerspace").filter(
            Q(target_makerspace__isnull=True)
            | Q(target_makerspace_id__in=visible_spaces)
        ).order_by("-created_at", "-pk")[:20]
        audit.record(
            request.user, "tenant_migration.imports_read", target=request.user,
            meta={"import_count": len(rows), "format_version": 1},
        )
        return Response(ImportJobSerializer(rows, many=True).data)

    @extend_schema(tags=["Tenant migration"], summary="Upload an age-encrypted archive and queue its staging", request=ImportCreateSerializer, responses={202: ImportJobSerializer, 400: FIELD_ERRORS, 409: CONFLICT, **AUTH_ERRORS})
    def post(self, request):
        serializer = ImportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        archive = serializer.validated_data["archive"]
        handler = self.import_upload_handler
        if (
            not isinstance(archive, PersistedImportUpload)
            or archive.persisted_path not in handler.created_paths
        ):
            raise ValidationError({"archive": ["Upload an archive file using multipart form data."]})
        try:
            job = accept_import_upload(
                actor=request.user,
                archive_path=archive.persisted_path, size=archive.size,
                source_archive_digest=serializer.validated_data["source_archive_digest"],
                expires_at=timezone.now() + timedelta(
                    seconds=settings.DATA_EXPORT_RETENTION_SECONDS
                ),
            )
        except Exception as exc:
            return protocol_error(exc)
        # accept_import_upload has committed, so the job row now owns the file.
        handler.transferred_paths.add(archive.persisted_path)
        # Brokerless deployments run tasks eagerly, which would stage inside this
        # request; the stale-PENDING sweep stages those jobs from the scheduler instead.
        if not settings.CELERY_TASK_ALWAYS_EAGER:
            try:
                stage_import_job_task.delay(str(job.pk), request.user.pk)
            except Exception:
                logger.exception(
                    "tenant_import_staging_dispatch_failed", extra={"job_id": str(job.pk)},
                )
        return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class TenantImportDetailView(MigrationAPIView):
    @extend_schema(tags=["Tenant migration"], summary="Read a tenant import job", responses={200: ImportJobSerializer, 404: NOT_FOUND, **AUTH_ERRORS})
    def get(self, request, job_id):
        job = _job(request.user, job_id)
        audit.record(
            request.user, "tenant_migration.import_read", target=job,
            meta={"import_id": str(job.pk), "format_version": 1},
        )
        return Response(ImportJobSerializer(job).data)


class TenantImportIdentityDecisionsView(MigrationAPIView):
    @extend_schema(tags=["Tenant migration"], summary="Read the exact archived identity decision list", responses={200: ClosureIdentitySerializer(many=True), 404: NOT_FOUND, 409: CONFLICT, **AUTH_ERRORS})
    def get(self, request, job_id):
        from .archive_stream import PortableArchive
        from .import_staging import decrypted_archive

        job = _job(request.user, job_id)
        try:
            rows_path = rows_archive_path(job)
            with decrypted_archive(
                rows_path, require_carried_keys=(str(rows_path) == job.archive_path),
            ) as (root, _carried):
                rows = list(PortableArchive(root).rows("accounts.User"))
        except Exception as exc:
            return protocol_error(exc)
        audit.record(
            request.user, "tenant_migration.identity_decisions_read", target=job,
            meta={
                "import_id": str(job.pk), "identity_count": len(rows),
                "format_version": 1,
            },
        )
        return Response(ClosureIdentitySerializer(rows, many=True).data)

    @extend_schema(tags=["Tenant migration"], summary="Submit all per-person import identity decisions", request=ImportDecisionListSerializer, responses={200: ImportJobSerializer, 400: FIELD_ERRORS, 409: CONFLICT, 404: NOT_FOUND, **AUTH_ERRORS})
    def post(self, request, job_id):
        job = _job(request.user, job_id)
        serializer = ImportDecisionListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = submit_identity_decisions(
                actor=request.user, job=job,
                decisions=serializer.validated_data["decisions"],
            )
        except Exception as exc:
            return protocol_error(exc)
        return Response(ImportJobSerializer(job).data)


class TenantImportRunView(MigrationAPIView):
    @extend_schema(tags=["Tenant migration"], summary="Run an identity-decided tenant import", description="Brokerless deployments run the persisted import request from the scheduler.", request=ImportRunSerializer, responses={202: ImportJobSerializer, 400: FIELD_ERRORS, 409: CONFLICT, 404: NOT_FOUND, 503: OpenApiResponse(description="Import worker unavailable."), **AUTH_ERRORS})
    def post(self, request, job_id):
        job = _job(request.user, job_id)
        serializer = ImportRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = claim_import_job(
                actor=request.user, job=job,
                target_identity=serializer.validated_data["target_identity"],
            )
        except Exception as exc:
            return protocol_error(exc)
        if settings.CELERY_TASK_ALWAYS_EAGER:
            return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
        try:
            run_import_job_task.delay(
                str(job.pk), request.user.pk, serializer.validated_data["target_identity"]
            )
        except Exception:
            TenantImportJob.objects.filter(pk=job.pk).update(
                status=TenantImportJob.Status.FAILED,
                failure_code="worker_unavailable",
                failure_detail="The tenant import worker is unavailable.",
                terminal_at=timezone.now(),
            )
            return Response(
                {"detail": "The tenant import worker is unavailable.", "code": "worker_unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class TenantImportVerificationView(MigrationAPIView):
    @extend_schema(tags=["Tenant migration"], summary="Read the import verification report", responses={200: VerificationReportSerializer, 404: NOT_FOUND, 409: CONFLICT, **AUTH_ERRORS})
    def get(self, request, job_id):
        job = _job(request.user, job_id)
        if not job.verification_report:
            return Response(
                {"detail": "The verification report is not available.", "code": "report_unavailable"},
                status=status.HTTP_409_CONFLICT,
            )
        audit.record(
            request.user, "tenant_migration.verification_read", target=job,
            meta={
                "import_id": str(job.pk),
                "model_count": len(job.verification_report.get("imported", {})),
                "format_version": job.verification_report.get("format_version", 0),
            },
        )
        return Response(VerificationReportSerializer(job.verification_report).data)
