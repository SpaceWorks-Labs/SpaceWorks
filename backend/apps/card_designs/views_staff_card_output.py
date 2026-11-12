"""Staff ID cards: number scheme, design, bulk print jobs, desk print and download (O-B4 part 2).

The design is the ordinary card design engine with the `staff_cards` domain: this app hands back (creating
on first use) the space's ONE staff design, and the existing `card-designs/<id>/...` routes edit, preview,
approve and publish it. Desk print and download use the same renderer as member cards.
"""
from django.http import HttpResponse
from django.utils.translation import gettext
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.makerspaces.platform import feature_enabled
from apps.openapi_errors import errors

from . import jobs, resolution, staff_card_numbering
from .models import CardJob
from .models_staff_cards import StaffCard
from .serializers import CardDesignSerializer, CardJobSerializer
from .serializers_staff_cards import (StaffCardJobCreateSerializer, StaffCardNumberingSerializer,
                                      StaffCardSettingsSerializer)
from .staff_card_access import card_for, space_for
from .stocks import STOCKS
from .switches import DESK_PRINT, STAFF_CARDS_AUTO

TAGS = ["Staff ID cards"]


def _settings(space):
    prefix, pattern = staff_card_numbering.current(space.pk)
    from . import numbering
    return {"prefix": prefix, "pattern": pattern, "preview": numbering.preview(prefix, pattern),
            "auto_issue": feature_enabled(space, STAFF_CARDS_AUTO), "desk_print": feature_enabled(space, DESK_PRINT)}


class StaffCardSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Staff card number scheme and the related switches", request=None,
                   responses={200: StaffCardSettingsSerializer, **errors(401, 404)})
    def get(self, request, makerspace_id):
        return Response(_settings(space_for(request.user, makerspace_id)))

    @extend_schema(tags=TAGS, summary="Save the staff card number scheme",
                   description="Separate from the member-card schemes. Tokens: {PREFIX}, {SEQ:n} once, {YYYY}, {YY}. "
                               "An empty pattern restores the default `STF-0001`. Audited.",
                   request=StaffCardNumberingSerializer, responses={200: StaffCardSettingsSerializer, **errors(400, 401, 404)})
    def put(self, request, makerspace_id):
        from apps.audit import services as audit
        space = space_for(request.user, makerspace_id)
        data = StaffCardNumberingSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = staff_card_numbering.save(space, data.validated_data["prefix"], data.validated_data["pattern"])
        audit.record(request.user, "staff_card.numbering_changed", makerspace=space, target=space,
                     meta={"prefix": row.prefix, "pattern": row.pattern})
        return Response(_settings(space))


class StaffCardDesignView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="The space's staff card design (created from the default template on first use)",
                   description="Edit it with the ordinary `card-designs/<id>` routes; staff cards render the PUBLISHED "
                               "document, or the shipped Classic template with a STAFF band until one is published.",
                   request=None, responses={200: CardDesignSerializer, **errors(401, 404)})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        design, _created = resolution.get_or_create(space, "staff_cards", actor=request.user)
        return Response(CardDesignSerializer(design, context={"request": request}).data)


class StaffCardJobListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="My staff-card print jobs in this space", request=None,
                   responses={200: CardJobSerializer(many=True), **errors(401, 404)})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        rows = CardJob.objects.filter(makerspace=space, scope="staff_cards",
                                      requested_by=request.user).order_by("-created_at")[:20]
        return Response(CardJobSerializer(rows, many=True).data)

    @extend_schema(tags=TAGS, summary="Queue a bulk staff-card job: print sheets, one PDF per person, or a ZIP",
                   request=StaffCardJobCreateSerializer,
                   responses={201: CardJobSerializer, 200: CardJobSerializer, **errors(400, 401, 404)})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        data = StaffCardJobCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        rows = StaffCard.objects.filter(makerspace=space, revoked_at__isnull=True, membership__isnull=False)
        if values.get("card_ids"):
            rows = rows.filter(pk__in=values["card_ids"])
        revision = list(space.card_designs.filter(domain="staff_cards").values_list("published_revision", flat=True))
        params = {"paper": values["paper"], "order": values["order"], "crop_marks": values["crop_marks"]}
        job, created = jobs.enqueue(request.user, space, values["kind"], scope="staff_cards",
                                    targets=list(rows.order_by("card_number").values_list("pk", flat=True)),
                                    params=params, revision=revision)
        return Response(CardJobSerializer(job).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class StaffCardPrintFaceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="One staff card face for desk printing (PNG, 300 dpi)",
                   description="Same contract as the member-card print face; audited once per card as "
                               "`staff_card.printed` (front face request). Off unless `membership.card_desk_print`.",
                   parameters=[OpenApiParameter("side", str, enum=["front", "back"]),
                               OpenApiParameter("stock", str, enum=sorted(STOCKS), required=False)],
                   request=None, responses={(200, "image/png"): OpenApiTypes.BINARY, **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        from . import staff_card_services as services
        from .cards import render
        from .views_print_face import fit_to_stock
        card = card_for(request.user, pk)
        if not feature_enabled(card.makerspace, DESK_PRINT):
            raise NotFound()
        if not card.is_active:
            raise PermissionDenied(gettext("A revoked card cannot be printed."))
        side, stock = request.query_params.get("side", "front"), request.query_params.get("stock")
        if side not in ("front", "back") or (stock and stock not in STOCKS):
            raise ValidationError({"detail": gettext("Choose the front or back, and a known stock.")})
        data, _type, filename = render("staff_card", card, fmt="png", side=side)
        if stock:
            data, _size = fit_to_stock(data, stock)
        if side == "front":
            services.record_print(request.user, card)
        response = HttpResponse(data, content_type="image/png")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response


class StaffCardDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Download a staff card (PDF, or one side as PNG)",
                   parameters=[OpenApiParameter("format", str, enum=["pdf", "png"]),
                               OpenApiParameter("side", str, enum=["front", "back"]),
                               OpenApiParameter("bleed_mm", float, description="Print-ready: 0-5 mm mirror bleed."),
                               OpenApiParameter("crop_marks", bool, description="Print-ready PDF: crop marks.")],
                   request=None, responses={(200, "application/pdf"): OpenApiTypes.BINARY,
                                            (200, "image/png"): OpenApiTypes.BINARY, **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        from .cards import render
        from .downloads import record_download
        card = card_for(request.user, pk)
        if not card.is_active:
            raise PermissionDenied(gettext("This card was revoked."))
        from .print_export import options_from_query
        fmt, side = request.query_params.get("format", "pdf"), request.query_params.get("side", "front")
        data, content_type, filename = render("staff_card", card, fmt=fmt, side=side, **options_from_query(request.query_params))
        record_download(request.user, "staff_card", card, fmt, side)
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["Cache-Control"] = "private, no-store"
        return response
