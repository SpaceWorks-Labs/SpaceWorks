"""Designer resources reached through a design the caller may edit: artwork uploads and
the card font library (list, prepare a family, and the font bytes the canvas loads)."""
from django.utils.translation import gettext
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.openapi_errors import errors
from .serializers_openapi import CardAssetUploadSerializer, FontPrepareRequestSerializer, FontPrepareResultSerializer

from . import assets, font_fetch, font_store, fonts
from .authority import design_for, require_edit
from .serializers import (CardAssetFinalizeSerializer, CardAssetPresignSerializer, CardAssetSerializer,
                          CardFontPageSerializer)

TAGS = ["Card designs"]


def _asset(row):
    return {"asset_id": str(row.asset_id), "kind": row.kind, "width_px": row.width_px, "height_px": row.height_px,
            "mean_colour": row.mean_colour, "ready": row.ready}


class CardAssetUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Start an artwork upload (staging presign only)",
                   request=CardAssetPresignSerializer,
                   responses={201: CardAssetUploadSerializer, **errors(400, 401, 403, 404, 503)})
    def post(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        data = CardAssetPresignSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            payload = assets.presign(request.user, design.makerspace, data.validated_data["kind"],
                                     data.validated_data["content_type"])
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(payload, status=status.HTTP_201_CREATED)


class CardAssetFinalizeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Finish an artwork upload: checked, re-encoded, stored privately",
                   request=CardAssetFinalizeSerializer,
                   responses={200: CardAssetSerializer, **errors(400, 401, 403, 404, 503)})
    def post(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        data = CardAssetFinalizeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            row = assets.finalize(request.user, design.makerspace, data.validated_data["asset_id"])
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(_asset(row))


class CardAssetContentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Artwork bytes for the designer canvas", request=None,
                   responses={(200, "image/png"): OpenApiTypes.BINARY, **errors(401, 403, 404)})
    def get(self, request, pk, asset_id):
        design = require_edit(request.user, design_for(request.user, pk))
        response = HttpResponse(assets.read(design.makerspace, asset_id), content_type="image/png")
        response["Cache-Control"] = "private, max-age=3600"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class CardFontListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Search the card font library", request=None,
                   parameters=[OpenApiParameter("q", str), OpenApiParameter("category", str),
                               OpenApiParameter("script", str), OpenApiParameter("offset", int)],
                   responses={200: CardFontPageSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        require_edit(request.user, design_for(request.user, pk))
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
        except ValueError:
            offset = 0
        count, rows = fonts.search(request.query_params.get("q", ""), category=request.query_params.get("category", ""),
                                   script=request.query_params.get("script", ""), offset=offset)
        return Response({"count": count, "results": [{**row, "weights": list(row["weights"]),
                                                      "scripts": list(row["scripts"]),
                                                      "state": font_fetch.state_of(row["family"])} for row in rows]})


class CardFontPrepareView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Fetch a catalogue family onto this server (a background task)",
                   request=FontPrepareRequestSerializer,
                   responses={202: FontPrepareResultSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        design = design_for(request.user, pk)
        require_edit(request.user, design)
        family = request.data.get("family")
        if not isinstance(family, str) or not fonts.family_weights(family):
            raise ValidationError({"family": gettext("That family is not in the card font library.")})
        pending = font_fetch.request_family(family)
        if pending:  # New platform-wide font rows were queued for download.
            from apps.audit import services as audit
            audit.record(request.user, "card_design.font_requested", makerspace=getattr(design, "makerspace", None),
                         target=design, meta={"family": family, "weights": len(pending)})
        return Response({"family": family, "pending_weights": pending, "state": font_fetch.state_of(family)},
                        status=status.HTTP_202_ACCEPTED)


class CardFontFileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, operation_id="admin_card_design_font_file",
                   summary="A card font file for the designer (served by this app, never Google)",
                   request=None, responses={(200, "font/ttf"): OpenApiTypes.BINARY, **errors(401, 403, 404)})
    def get(self, request, pk, family_slug, weight):
        require_edit(request.user, design_for(request.user, pk))
        family = fonts.canonical(next((name for name in [*fonts.BRAND, *fonts.LEGACY_FAMILIES, *fonts.catalogue(),
                                                         *fonts.bundled_noto()] if fonts.slug(name) == family_slug), None))
        data = font_store.font_bytes(family, weight) if family else None
        if data is None:
            raise NotFound()
        response = HttpResponse(data, content_type="font/ttf")
        response["Cache-Control"] = "private, max-age=86400"
        return response
