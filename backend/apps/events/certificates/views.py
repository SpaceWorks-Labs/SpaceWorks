from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.event_permissions import CHECK_IN, EDIT_DETAILS
from apps.events.credentials.views import ERRORS, CommandResultSerializer
from apps.events.models_certificates import EventAttendanceCertificate
from apps.events.throttles import CredentialRenderThrottle
from apps.events.profile_photos.views import private
from . import batches, print_workflow
from .badge_designs import save_design
from .models import CertificateIssueBatch
from .print_models import BadgePrintJob
from .serializers import (BulkIssueSerializer, BatchSerializer, PrintCreateSerializer, PrintDetailSerializer,
                          PrintAcceptedSerializer, BadgeDesignSerializer, BadgeDesignResultSerializer,
                          CertificateActionSerializer, CertificateEligibilitySerializer, SeedPageSerializer)


class CertificateEligibilityView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificates"], responses={200: CertificateEligibilitySerializer, **ERRORS})
    def get(self, request, pk):
        from apps.events.models_registration import EventRegistration
        event = event_authority.get_event(request.user, pk, None)
        count = EventRegistration.objects.filter(event=event, status="attended", member__isnull=False).count()
        return private(Response({"eligible_count": count, "event_version": event.version,
            "disclosure": "Public verification publishes only the event title, date and valid or revoked status."}))


class BulkIssueView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Event certificates"], request=BulkIssueSerializer, responses={202: BatchSerializer, **ERRORS})
    def post(self, request, pk):
        serializer = BulkIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        batch = batches.enqueue(pk, actor=request.user, **values)
        return private(Response(batches.project(batch), status=202))


class BatchView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificates"], responses={200: BatchSerializer, **ERRORS})
    def get(self, request, pk, batch_id):
        event = event_authority.get_event(request.user, pk, None)
        return private(Response(batches.project(get_object_or_404(CertificateIssueBatch, pk=batch_id, event=event))))


class PrintCreateView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Event credentials"], request=PrintCreateSerializer, responses={202: PrintAcceptedSerializer, **ERRORS})
    def post(self, request, pk):
        serializer = PrintCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event_authority.get_event(request.user, pk, CHECK_IN)
        job = print_workflow.create(pk, actor=request.user, **serializer.validated_data)
        job = print_workflow.render(job, actor=request.user)
        return private(Response({"job_id": job.pk, "state": job.state,
            "status_url": f"/api/v1/admin/events/{pk}/badges/print-jobs/{job.pk}/",
            "row_failures": job.row_failures}, status=202))


class PrintDetailView(APIView):
    permission_classes = [IsActiveStaff]

    def job(self, request, pk, job_id):
        from .print_policy import require_job
        event = event_authority.get_event(request.user, pk, CHECK_IN)
        job = get_object_or_404(BadgePrintJob, event=event, pk=job_id)
        require_job(job, request.user)
        return job

    @extend_schema(tags=["Event credentials"], responses={200: PrintDetailSerializer, **ERRORS})
    def get(self, request, pk, job_id):
        job = self.job(request, pk, job_id)
        return private(Response({"job_id": job.pk, "state": job.state,
                                 "row_failures": job.row_failures, "expires_at": job.expires_at}))


class DeskDesignView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event credentials"], responses={200: BadgeDesignResultSerializer, **ERRORS})
    def get(self, request, pk):
        from .print_models import EventBadgeTemplateRevision
        from rest_framework.exceptions import NotFound
        event = event_authority.get_event(request.user, pk, CHECK_IN)
        row = EventBadgeTemplateRevision.objects.filter(event=event).order_by("-pk").first()
        if not row:
            raise NotFound()
        return private(Response({"id": row.pk, "stock": row.stock, "document": row.document, "event_version": event.version}))


class PrintDownloadView(PrintDetailView):
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Event credentials"], responses={(200, "application/pdf"): OpenApiTypes.BINARY, **ERRORS})
    def get(self, request, pk, job_id):
        from apps.accounts.models import User
        from apps.events.credentials.streaming import private_bytes
        from .print_policy import require_job
        job = self.job(request, pk, job_id)
        content = print_workflow.download(job, actor=request.user)
        def authorize():
            from rest_framework.exceptions import NotFound
            try:
                job.refresh_from_db()
            except BadgePrintJob.DoesNotExist as exc:
                raise NotFound() from exc
            actor = User.objects.filter(pk=request.user.pk).first()
            if actor is None:
                raise NotFound()
            require_job(job, actor)
        return private_bytes(request, content, authorize=authorize, expires_at=job.expires_at,
                             mime="application/pdf", locator_key=job.object_key, filename=f"event-{pk}-badges.pdf")


class BadgeDesignView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event credentials"], responses={200: SeedPageSerializer, **ERRORS})
    def get(self, request, pk):
        from .seeds import catalogue
        from .layout import DESIGN_STOCK_CHOICES, STOCKS
        from rest_framework.exceptions import ValidationError
        event_authority.get_event(request.user, pk, EDIT_DETAILS)
        stock, theme = request.query_params.get("stock", "cr80-landscape"), request.query_params.get("theme", "light")
        if stock not in DESIGN_STOCK_CHOICES or theme not in ("light", "dark"):
            raise ValidationError("Choose a named stock and light/dark theme.")
        # Packaged default designs exist for the six frozen stocks only; A6 landscape and custom start blank.
        rows = catalogue(kind="badge", theme=theme, stock=stock) if stock in STOCKS else []
        return private(Response({"count": len(rows), "next": None, "previous": None, "results": rows}))

    @extend_schema(tags=["Event credentials"], request=BadgeDesignSerializer,
                   responses={201: BadgeDesignResultSerializer, **ERRORS},
                   description="Import/save a person-free design. Typed photo/QR slots only; no real data or external URLs.")
    def post(self, request, pk):
        serializer = BadgeDesignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = save_design(pk, actor=request.user, **serializer.validated_data)
        return private(Response({"id": row.pk, "stock": row.stock, "document": row.document, "event_version": row.event_version}, status=201))


class CertificateRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificates"], request=CertificateActionSerializer,
                   responses={200: CommandResultSerializer, **ERRORS})
    def post(self, request, pk, certificate_id):
        from .commands import change_certificate
        serializer = CertificateActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = change_certificate(pk, certificate_id, actor=request.user, action="revoke", **serializer.validated_data)
        return private(Response(result))


class CertificateReissueView(CertificateRevokeView):
    @extend_schema(tags=["Event certificates"], request=CertificateActionSerializer,
                   responses={200: CommandResultSerializer, **ERRORS})
    def post(self, request, pk, certificate_id):
        from .commands import change_certificate
        serializer = CertificateActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return private(Response(change_certificate(pk, certificate_id, actor=request.user,
                                  action="reissue", **serializer.validated_data)))
