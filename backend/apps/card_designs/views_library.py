"""The space's artwork library and brand kit, reached through a design the caller may edit (decision 344(b))."""
from django.utils.translation import gettext
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import asset_library, brand_kit, csv_merge
from .authority import design_for, require_edit
from .serializers_library import (CardBarcodeRequestSerializer, CardBarcodeSerializer, CardBrandKitSerializer,
                                  CardCsvMergeReportSerializer, CardCsvMergeSerializer, CardLibraryAssetSerializer)

TAGS = ["Card designs"]
KINDS = ("background", "watermark", "image")


class CardAssetLibraryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="The space's uploaded artwork, newest first (reuse in any design)",
                   parameters=[OpenApiParameter("kind", str, enum=list(KINDS), required=False)], request=None,
                   responses={200: CardLibraryAssetSerializer(many=True), **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        kind = request.query_params.get("kind") or None
        if kind and kind not in KINDS:
            raise ValidationError({"kind": gettext("Use background, watermark or image.")})
        rows = asset_library.list_assets(design.makerspace, kind)
        return Response(CardLibraryAssetSerializer(rows, many=True).data)


class CardAssetDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Delete an unused picture from the space's library (gives its storage back)",
                   description="Refused (400, `asset_in_use`) while a design, a saved version or a template uses it. "
                               "Audited as `card_design.asset_deleted`.",
                   request=None, responses={204: None, **errors(400, 401, 403, 404)})
    def delete(self, request, pk, asset_id):
        design = require_edit(request.user, design_for(request.user, pk))
        asset_library.delete_asset(request.user, design.makerspace, asset_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CardBrandKitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="The space's brand kit: its colours, logo slots and the allowed fonts",
                   request=None, responses={200: CardBrandKitSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        return Response(CardBrandKitSerializer(brand_kit.build(design)).data)


class CardCsvMergeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "card_render"  # up to 200 cards drawn in the request: the same budget as the other renders

    @extend_schema(tags=TAGS, summary="Bulk cards from a CSV: check it (dry run) or print the published design per row",
                   description="Rows hold merge values only: such cards have no record, so their check, desk and "
                               "check-in QR codes print nothing and photos print initials. Audited as "
                               "`card_design.csv_merged`.",
                   request=CardCsvMergeSerializer,
                   responses={200: CardCsvMergeReportSerializer, (200, "application/pdf"): OpenApiTypes.BINARY,
                              **errors(400, 401, 403, 404, 429)})
    def post(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        data = CardCsvMergeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if values["dry_run"]:
            columns, unknown, rows = csv_merge.parse(values["csv"])
            return Response(CardCsvMergeReportSerializer({
                "columns": columns, "unknown_columns": unknown, "rows": len(rows),
                "preview": rows[:csv_merge.PREVIEW_ROWS], "published": design.published_document is not None,
                "images": csv_merge.preview_images(design, rows)}).data)
        pdf = csv_merge.render(request.user, design, values["csv"], paper=values["paper"], order=values["order"],
                               crop_marks=values["crop_marks"])
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="card-design-{design.pk}-csv.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response


class CardBarcodeView(APIView):
    """The designer draws barcodes from the server's own encoding, so the preview carries the modules print uses."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Encode a barcode for the designer preview (same encoder as print)",
                   description="A value the symbology cannot carry (an EAN-13 needs 12-13 digits, UPC-A 11-12) previews "
                               "the symbology's sample, exactly like the server's preview render.",
                   request=CardBarcodeRequestSerializer, responses={200: CardBarcodeSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from .barcode_symbols import encode
        from .rendering_extras import SAMPLES
        require_edit(request.user, design_for(request.user, pk))
        data = CardBarcodeRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        symbology, value = data.validated_data["symbology"], data.validated_data["value"]
        encoded = encode(symbology, value) or encode(symbology, SAMPLES.get(symbology, "SW-0000"))
        return Response(CardBarcodeSerializer(encoded).data)
