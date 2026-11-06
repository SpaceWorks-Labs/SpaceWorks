"""Design actions: publish, submit for approval, approve/reject, reset, export/import, preview."""
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.openapi_errors import errors
from .serializers_openapi import CardDesignFileSerializer

from . import design_file, designs
from .authority import acted_for, design_for, require_edit
from .default_templates import build
from .serializers import (CardDesignDecisionSerializer, CardDesignImportResultSerializer, CardDesignImportSerializer,
                          CardDesignResetSerializer, CardDesignSerializer, CardPreviewSerializer)

TAGS = ["Card designs"]


def _design(request, design):
    design.refresh_from_db()
    return Response(CardDesignSerializer(design, context={"request": request}).data)


class CardDesignPublishView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Publish the current revision", description="Refused when this design needs "
                   "approval for the caller (#128 C-28, #136); event designs publish directly for every organiser.",
                   request=None, responses={200: CardDesignSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        return _design(request, designs.publish(request.user, design, acted_for=acted_for(request.user, design)))


class CardDesignSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Submit the current revision for approval", request=None,
                   responses={200: CardDesignSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        designs.submit(request.user, design)
        return _design(request, design)


class CardDesignApproveView(APIView):
    permission_classes = [IsAuthenticated]
    approve = True

    @extend_schema(tags=TAGS, summary="Approve and publish a submitted design (approvers only)",
                   request=CardDesignDecisionSerializer, responses={200: CardDesignSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        design = design_for(request.user, pk)
        data = CardDesignDecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        designs.decide(request.user, design, approve=self.approve, note=data.validated_data.get("note", ""))
        return _design(request, design)


class CardDesignRejectView(CardDesignApproveView):
    approve = False

    @extend_schema(tags=TAGS, summary="Send a submitted design back with a note (approvers only)",
                   request=CardDesignDecisionSerializer, responses={200: CardDesignSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        return super().post(request, pk)


class CardDesignResetView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Start the draft again from one of the six templates",
                   request=CardDesignResetSerializer, responses={200: CardDesignSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        data = CardDesignResetSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return _design(request, designs.reset(request.user, design, build(
            data.validated_data["template"], design.domain, data.validated_data["theme"])))


class CardDesignExportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Download the design file (JSON)", request=None,
                   responses={(200, "application/json"): CardDesignFileSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        audit.record(request.user, "card_design.exported", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk})
        response = Response(design_file.export(design))
        response["Content-Disposition"] = f'attachment; filename="card-design-{design.pk}.json"'
        return response


class CardDesignImportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Import a design file into this design's draft",
                   description="Accepts `spaceworks-card-design` v2 and two older badge formats as file formats. "
                               "Uploaded artwork never travels; notes list what was dropped.",
                   request=CardDesignImportSerializer,
                   responses={200: CardDesignImportResultSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        from .models import CardDesignAsset
        design = require_edit(request.user, design_for(request.user, pk))
        data = CardDesignImportSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        document, notes = design_file.parse(data.validated_data["file"])
        owned = {str(value) for value in CardDesignAsset.objects.filter(makerspace=design.makerspace, ready=True)
                 .values_list("asset_id", flat=True)}
        notes += design_file.strip_foreign_assets(document, owned)
        design = designs.save(request.user, design, document, expected_revision=design.revision)
        audit.record(request.user, "card_design.imported", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk})
        design.refresh_from_db()
        return Response({"design": CardDesignSerializer(design, context={"request": request}).data, "notes": notes})


class CardDesignPreviewView(APIView):
    """A watermarked render of an UNSAVED document with sample people (short or long names)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Preview an unsaved design (watermarked PNG or PDF)",
                   description="Sample people (short or long names), or `holder_id`: one real person this design "
                               "prints (from the holders list), without their opt-in extras. Audited for a holder.",
                   request=CardPreviewSerializer,
                   responses={(200, "image/png"): OpenApiTypes.BINARY, (200, "application/pdf"): OpenApiTypes.BINARY,
                              **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from .cards import sample_context
        from .rendering import render_pdf, render_png
        design = require_edit(request.user, design_for(request.user, pk))
        space = design.makerspace
        data = CardPreviewSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        document = designs.validated(space.pk, values["document"], check_contrast=False)
        if values.get("holder_id"):
            from . import holder_samples
            kind, card = holder_samples.holder(request.user, design, values["holder_id"])
            context = holder_samples.preview_context(kind, card, document)
            audit.record(request.user, "card_design.previewed_as_holder", makerspace=space, target=design,
                         meta={"design_id": design.pk, "holder_kind": kind, "holder_id": card.pk})
        else:
            context = sample_context(space, document, long=values["long_names"])
        if values["format"] == "pdf":
            return HttpResponse(render_pdf(document, context, title="Card preview"), content_type="application/pdf")
        return HttpResponse(render_png(document, context, side=values["side"], dpi=150), content_type="image/png")
