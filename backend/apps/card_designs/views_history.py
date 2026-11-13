"""Version history and restore, the "Preview as" holder picker, and the calibration sheet."""
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import calibration, designs, history, holder_samples
from .authority import acted_for, design_for, require_edit
from .serializers import CardDesignSerializer
from .serializers_history import (CardDesignRestoreSerializer, CardDesignRevisionDetailSerializer,
                                  CardDesignRevisionPageSerializer, CardHolderSampleSerializer)

TAGS = ["Card designs"]


class RevisionPagination(PageNumberPagination):
    page_size = 24


class CardDesignRevisionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Version history: every saved revision, newest first",
                   parameters=[OpenApiParameter("page", int)], request=None,
                   responses={200: CardDesignRevisionPageSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        design = design_for(request.user, pk)
        rows, approvals = history.revisions(design)
        paginator = RevisionPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response([history.describe(row, design, approvals) for row in page])


class CardDesignRevisionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="One saved revision's document, to preview before restoring", request=None,
                   responses={200: CardDesignRevisionDetailSerializer, **errors(401, 403, 404)})
    def get(self, request, pk, revision):
        design = design_for(request.user, pk)
        row = history.revision(design, revision)
        _rows, approvals = history.revisions(design)
        return Response({**history.describe(row, design, approvals), "document": row.document})


class CardDesignRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Restore a saved revision as the new draft",
                   description="Saves the old document as a NEW revision (history is never rewritten) with "
                               "compare-and-swap on the current revision; cards keep the published version until "
                               "you publish. Audited `card_design.restored`.",
                   request=CardDesignRestoreSerializer,
                   responses={200: CardDesignSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk, revision):
        design = require_edit(request.user, design_for(request.user, pk))
        data = CardDesignRestoreSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        restored = history.restore(request.user, design, revision, expected_revision=data.validated_data["revision"],
                                   acted_for=acted_for(request.user, design))
        restored.refresh_from_db()
        return Response(CardDesignSerializer(restored, context={"request": request}).data)


class CardDesignHolderListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="People with a live card this design prints (for \"Preview as\")",
                   description="The 30 newest live cards the design applies to. Names are masked for a "
                               "superadmin without a PII window; ticket designs have none.", request=None,
                   responses={200: CardHolderSampleSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        kind, cards = holder_samples.holders(design)
        rows = [holder_samples.row(kind, card) for card in cards]
        serializer = CardHolderSampleSerializer(rows, many=True, context={"request": request,
                                                                          "makerspace_id": design.makerspace_id})
        return Response(serializer.data)


class CardDesignCalibrationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Print calibration sheet (PDF) for this design's card size",
                   parameters=[OpenApiParameter("paper", str, enum=list(calibration.PAPERS))], request=None,
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        design = design_for(request.user, pk)
        document = designs.validated(design.makerspace_id, design.document, check_contrast=False)
        pdf = calibration.render(document, request.query_params.get("paper", "a4"))
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="calibration-{document["stock"]}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response
