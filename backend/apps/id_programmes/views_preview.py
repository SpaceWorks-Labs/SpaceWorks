"""Batch print preview for a programme's approved cards (the first sheet, before a job)."""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.card_designs import sheet_preview
from apps.card_designs.serializers_history import SheetPreviewRequestSerializer, SheetPreviewSerializer
from apps.card_designs.views_jobs import job_params
from apps.card_designs.views_sheet_preview import DESCRIPTION
from apps.openapi_errors import errors

from .access import MANAGE, programme_for

TAGS = ["ID programmes"]


class ProgrammeSheetPreviewView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "card_render"

    @extend_schema(tags=TAGS, summary="Preview the first print sheet of a programme bulk job", description=DESCRIPTION,
                   request=SheetPreviewRequestSerializer,
                   responses={200: SheetPreviewSerializer, **errors(400, 401, 403, 404, 429)})
    def post(self, request, pk):
        programme = programme_for(request.user, pk, MANAGE)
        data = SheetPreviewRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        rows = programme.cards.filter(status="approved")
        if values.get("card_ids"):
            rows = rows.filter(pk__in=values["card_ids"])
        ids = list(rows.order_by("sequence", "pk").values_list("pk", flat=True))
        return Response(sheet_preview.preview(request.user, programme.makerspace, "programme_card", ids,
                                              job_params(values), scope="id_programme"))
