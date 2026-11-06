"""Staff issue routes (C10): plan who gets which certificate, sample render, issued list and PNG."""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.credentials.views import ERRORS
from apps.events.models_certificates import EventAttendanceCertificate
from apps.events.profile_photos.views import private
from apps.events.throttles import CredentialRenderThrottle
from . import holder, issue_plan
from .merge import frozen_merge, kind_title
from .output_serializers import (CertificateIssuePlanRequestSerializer, CertificateIssuePlanSerializer, IssuedCertificatePageSerializer,
                                 CertificatePlannedSubjectSerializer)
from .output_views import png_response

TAGS = ["Event certificates"]
PAGE = 50


def _context(request, event):
    return {"request": request, "makerspace_id": event.makerspace_id}


class IssuedCertificatesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, responses={200: IssuedCertificatePageSerializer, **ERRORS},
                   parameters=[OpenApiParameter("page", int, required=False),
                               OpenApiParameter("kind", str, required=False), OpenApiParameter("status", str, required=False)],
                   description="Every certificate issued for this event (50 per page), newest first, with kind and status.")
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, None)
        rows = EventAttendanceCertificate.objects.filter(event=event).select_related("award").order_by("-issued_at", "-pk")
        for key in ("kind", "status"):
            if request.query_params.get(key):
                rows = rows.filter(**{key: request.query_params[key]})
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except ValueError:
            page = 1
        total = rows.count()
        data = [{"id": row.pk, "recipient_name": row.recipient_name, "kind": row.kind, "kind_title": kind_title(row.kind),
                 "award": frozen_merge(row).get("award", ""), "status": row.status, "revision": row.revision,
                 "issued_at": row.issued_at, "public_verification_enabled": row.public_verification_enabled,
                 "revocation_reason": row.revocation_reason} for row in rows[(page - 1) * PAGE:page * PAGE]]
        body = {"count": total, "next": str(page + 1) if page * PAGE < total else None,
                "previous": str(page - 1) if page > 1 else None, "results": data}
        return private(Response(IssuedCertificatePageSerializer(body, context=_context(request, event)).data))


class IssuedCertificatePngView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=TAGS, responses={(200, "image/png"): OpenApiResponse(OpenApiTypes.BINARY), **ERRORS},
                   description="An issued certificate as a 300 dpi PNG, rasterised from its PDF. Audited.")
    def get(self, request, pk, certificate_id):
        from .outputs import certificate_png
        event = event_authority.get_event(request.user, pk, None)
        row = get_object_or_404(EventAttendanceCertificate, pk=certificate_id, event=event)
        if row.status != "active":
            raise NotFound()
        content = certificate_png(row)
        holder.record_png(row, actor=request.user)
        return png_response(content, f"certificate-{row.serial}.png")


class IssuePlanView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=TAGS, request=CertificateIssuePlanRequestSerializer, responses={200: CertificateIssuePlanSerializer, **ERRORS},
                   description="Who would receive which certificate (attendance, participants, award winners and "
                               "finalists from published results, role thank-yous), and who is skipped and why. "
                               "Writes nothing; confirm through the bulk issue command.")
    def post(self, request, pk):
        event = event_authority.get_event(request.user, pk, None)
        serializer = CertificateIssuePlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = issue_plan.plan(event, actor=request.user, groups=serializer.validated_data["groups"])
        return private(Response(CertificateIssuePlanSerializer(result, context=_context(request, event)).data))


class IssueSampleView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=TAGS, request=CertificatePlannedSubjectSerializer,
                   responses={(200, "application/pdf"): OpenApiResponse(OpenApiTypes.BINARY), **ERRORS},
                   description="Render one planned recipient's certificate with the design their kind uses. Not stored.")
    def post(self, request, pk):
        from apps.events.certificate_rendering import render_certificate_pdf
        event = event_authority.get_event(request.user, pk, None)
        serializer = CertificatePlannedSubjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        context = issue_plan.sample_context(event, actor=request.user, subject=dict(serializer.validated_data))
        return private(HttpResponse(render_certificate_pdf(context), content_type="application/pdf"))
