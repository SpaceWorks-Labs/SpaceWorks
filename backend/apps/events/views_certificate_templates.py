from django.utils.translation import gettext
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.models import EventCertificateArtwork
from apps.events.certificate_templates import DEFAULT_CERTIFICATE_TEMPLATE, read_parameters
from apps.events.certificate_rendering import render_certificate_pdf
from apps.events import certificate_artwork_storage as storage
from apps.events.services_certificate_templates import (
    require_design, save_template, reserve_artwork, finalize_artwork, preview_context,
)
from apps.events.serializers_certificate_templates import (
    CertificateTemplateWriteSerializer, CertificateTemplateRevisionSerializer,
    CertificateTemplateCommandSerializer, CertificateTemplateCommandResultSerializer,
    CertificateArtworkPresignSerializer, CertificateArtworkUploadSerializer, CertificateArtworkSerializer,
    CertificatePreviewSerializer, KIND_CHOICES,
)
from apps.events.serializers_staff_tools import StrictSerializer
from apps.events.throttles import CertificateArtworkThrottle, CredentialRenderThrottle
from apps.hardware_requests.exceptions import ErrorSerializer

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 429, 503)}
PDF = OpenApiResponse(OpenApiTypes.BINARY, description="Private server-rendered certificate preview.")


def _event(request, pk):
    event = event_authority.get_event(request.user, pk, EDIT_DETAILS)
    require_design(event, request.user)
    return event


def _private(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class EventCertificateTemplateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], responses={200: CertificateTemplateRevisionSerializer, **ERRORS},
                   parameters=[OpenApiParameter("kind", str, enum=list(KIND_CHOICES[1:]), required=False,
                                                description="Read this certificate kind's design; it falls back to the event default.")],
                   description="Current immutable revision or default layout. Requires live edit_details and events.certificate_designer.")
    def get(self, request, pk):
        from rest_framework.exceptions import ValidationError
        event = _event(request, pk)
        kind = request.query_params.get("kind", "")
        if kind not in KIND_CHOICES:
            raise ValidationError({"kind": gettext("Choose a certificate kind.")})
        revisions = event.certificate_template_revisions
        own = revisions.filter(certificate_kind=kind).first() if kind else None
        revision = own or revisions.filter(certificate_kind="").first()
        data = (CertificateTemplateRevisionSerializer(revision).data if revision else
                {"id": None, "parameters": DEFAULT_CERTIFICATE_TEMPLATE,
                 "artwork_id": None, "created_at": None})
        data["parameters"] = read_parameters(revision.parameters if revision else {},
                                              has_artwork=bool(revision and revision.artwork_id))
        data["event_version"] = event.version
        data["certificate_kind"] = kind
        data["uses_default"] = bool(kind) and own is None
        data["own_designs"] = sorted(set(revisions.exclude(certificate_kind="").values_list("certificate_kind", flat=True)))
        return _private(Response(data))

    @extend_schema(tags=["Admin events"], request=CertificateTemplateWriteSerializer,
                   responses={201: CertificateTemplateRevisionSerializer, **ERRORS},
                   description="Create a new immutable revision. Artwork must be promoted and owned by this event; issuance snapshots never change.")
    def post(self, request, pk):
        event = _event(request, pk)
        serializer = CertificateTemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revision = save_template(event, actor=request.user, **serializer.validated_data)
        return _private(Response(CertificateTemplateRevisionSerializer(revision).data, status=201))

    @extend_schema(tags=["Admin events"], request=CertificateTemplateCommandSerializer,
                   responses={200: CertificateTemplateCommandResultSerializer, **ERRORS})
    def put(self, request, pk):
        from .certificates.template_commands import save_command
        _event(request, pk)
        serializer = CertificateTemplateCommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _private(Response(save_command(pk, actor=request.user, **serializer.validated_data)))


class EventCertificatePreviewView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Admin events"], request=CertificatePreviewSerializer,
                   responses={(200, "application/pdf"): PDF, **ERRORS},
                   description="Preview with a sample recipient (the staff-typed sample name is never stored); same geometry, artwork and overflow rules as issuance. Kind labels and signatures use samples.")
    def post(self, request, pk):
        event = _event(request, pk)
        serializer = CertificatePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        context = preview_context(event, actor=request.user, **serializer.validated_data)
        return _private(HttpResponse(render_certificate_pdf(context), content_type="application/pdf"))


class EventCertificateArtworkPresignView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CertificateArtworkThrottle]

    @extend_schema(tags=["Admin events"], request=CertificateArtworkPresignSerializer,
                   responses={201: CertificateArtworkUploadSerializer, **ERRORS},
                   description="Reserve owned private artwork and issue a ten-minute staging-only PUT. PNG/JPEG, at most 10 MiB. Final bytes are server-owned.")
    def post(self, request, pk):
        event = _event(request, pk)
        serializer = CertificateArtworkPresignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        values.pop("purpose", None)
        row, url = reserve_artwork(event, actor=request.user, **values)
        return _private(Response({"id": row.pk, "upload_url": url,
                                  "headers": {"Content-Type": values["content_type"]}}, status=201))


class EventCertificateArtworkFinalizeView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CertificateArtworkThrottle]

    @extend_schema(tags=["Admin events"], request=StrictSerializer,
                   responses={200: CertificateArtworkSerializer, **ERRORS},
                   description="Validate bounded decoded pixels, strip metadata and promote exactly once. Quota and authority rechecked on attachment. Retries are idempotent.")
    def post(self, request, pk, artwork_id):
        event = _event(request, pk)
        serializer = StrictSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = finalize_artwork(event, artwork_id, actor=request.user)
        return _private(Response({"id": row.pk, "resource_id": str(row.resource_id)}))


class EventCertificateArtworkView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Admin events"], responses={(200, "image/png"): OpenApiTypes.BINARY, **ERRORS},
                   description="Read private artwork with live event edit authority; no public artwork route or object URL.")
    def get(self, request, pk, artwork_id):
        event = _event(request, pk)
        row = get_object_or_404(EventCertificateArtwork, event=event, pk=artwork_id, promoted_at__isnull=False)
        payload = storage.read_artwork(row.object_key, row.version_id, row.sha256)
        return _private(HttpResponse(payload, content_type="image/png"))


class EventCertificateArtworkByResourceView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Admin events"], responses={(200, "image/png"): OpenApiTypes.BINARY, **ERRORS},
                   description="Read private artwork by the `resource_id` that certificate image layers store, with the same live event "
                               "edit authority as the numeric route; artwork of another event or space is a 404.")
    def get(self, request, pk, resource_id):
        event = _event(request, pk)
        row = get_object_or_404(EventCertificateArtwork, event=event, resource_id=resource_id, promoted_at__isnull=False)
        payload = storage.read_artwork(row.object_key, row.version_id, row.sha256)
        return _private(HttpResponse(payload, content_type="image/png"))
