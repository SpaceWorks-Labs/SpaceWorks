"""Event/version-bound default artwork installation and server PDF previews."""
from io import BytesIO
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.admin_api.permissions import IsActiveStaff
from apps.audit.services import record
from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS
from apps.events.credentials.views import ERRORS, CredentialCommandSerializer
from apps.events.profile_photos.views import private
from apps.events.throttles import CredentialRenderThrottle
from apps.events.serializers_staff_tools import StrictSerializer
from .layout import STOCKS
from .serializers import SeedPageSerializer
from .seeds import catalogue, install_to_event


class SeedSelectionSerializer(StrictSerializer):
    kind = serializers.ChoiceField(choices=("badge", "certificate"))
    theme = serializers.ChoiceField(choices=("light", "dark"))
    seed_id = serializers.CharField(max_length=100)
    seed_version = serializers.IntegerField(min_value=1)
    stock = serializers.ChoiceField(choices=tuple(STOCKS), allow_null=True, required=False, default=None)


class SeedInstallSerializer(SeedSelectionSerializer, CredentialCommandSerializer):
    pass


class SeedInstalledSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    event_version = serializers.IntegerField()
    kind = serializers.CharField()
    document = serializers.DictField()
    stock = serializers.CharField(allow_null=True)


def resolve(values):
    if values["kind"] == "badge" and values["stock"] is None:
        raise serializers.ValidationError({"stock": "Choose a badge stock."})
    rows = catalogue(kind=values["kind"], theme=values["theme"], stock=values["stock"])
    row = next((row for row in rows if row["seed_id"] == values["seed_id"]
                and row["seed_version"] == values["seed_version"]), None)
    if row is None:
        raise serializers.ValidationError({"seed_id": "Reload the current default designs."})
    return row


class SeedCatalogueView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event certificates"], parameters=[OpenApiParameter("kind", str), OpenApiParameter("theme", str), OpenApiParameter("stock", str)], responses={200: SeedPageSerializer, **ERRORS})
    def get(self, request, pk):
        event_authority.get_event(request.user, pk, EDIT_DETAILS)
        kind, theme = request.query_params.get("kind", "certificate"), request.query_params.get("theme", "light")
        stock = request.query_params.get("stock")
        if kind not in ("certificate", "badge") or theme not in ("light", "dark") or (kind == "badge" and stock not in STOCKS):
            raise serializers.ValidationError("Choose a supported kind, theme and badge stock.")
        rows = catalogue(kind=kind, theme=theme, stock=stock)
        return private(Response({"count": len(rows), "next": None, "previous": None, "results": rows}))


class SeedInstallView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Event certificates"], request=SeedInstallSerializer,
                   responses={201: SeedInstalledSerializer, **ERRORS})
    def post(self, request, pk):
        serializer = SeedInstallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        from uuid import UUID
        try:
            header = UUID(request.headers.get("Idempotency-Key", ""))
        except (ValueError, TypeError, AttributeError):
            raise serializers.ValidationError({"operation_id": "Idempotency-Key must equal operation_id."})
        if header != values["operation_id"]:
            raise serializers.ValidationError({"operation_id": "Idempotency-Key must equal operation_id."})
        resolve(values)
        row = install_to_event(pk, actor=request.user, **values)
        event = event_authority.get_event(request.user, pk, EDIT_DETAILS)
        return private(Response({"id": row.pk, "event_id": pk, "event_version": event.version,
            "kind": values["kind"], "document": row.document if values["kind"] == "badge" else row.parameters,
            "stock": values["stock"]}, status=201))


class SeedPreviewView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [CredentialRenderThrottle]

    @extend_schema(tags=["Event certificates"], request=SeedSelectionSerializer,
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, **ERRORS})
    def post(self, request, pk):
        event = event_authority.get_event(request.user, pk, EDIT_DETAILS)
        serializer = SeedSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        seed = resolve(serializer.validated_data)
        document = seed["document"]
        from reportlab.lib.units import mm
        from reportlab.pdfgen.canvas import Canvas
        from .layer_rendering import draw_document, QrResource
        from .rendering import badge_image_resource
        output = BytesIO()
        canvas = Canvas(output, pagesize=(document["page_width_mm"]*mm, document["page_height_mm"]*mm), invariant=1)
        def resource(layer):
            if layer["type"] == "image":
                return badge_image_resource(layer, event_id=event.pk, document=document)
            if layer["type"] in ("certificate_qr", "event_credential_qr"):
                return QrResource("SAMPLE", dummy=True)
            return None
        draw_document(canvas, document, {"name": "Sample participant", "event": "Sample event",
            "eventDate": "18 October 2026", "organisation": "Space Works", "issueDate": "18 October 2026",
            "certificate_id": "SAMPLE"}, resource, preview=True)
        canvas.showPage()
        canvas.save()
        record(request.user, "event.badge_design_previewed", makerspace=event.makerspace, target=event,
            meta={"seed_id": seed["seed_id"], "seed_version": seed["seed_version"]})
        return private(HttpResponse(output.getvalue(), content_type="application/pdf"))
