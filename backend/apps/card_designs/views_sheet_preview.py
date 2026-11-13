"""Batch print preview for a space's member cards: the first sheet before the job is queued.

Programme and event cards have the same preview on their own routes (their apps own the
authority checks); all three call `sheet_preview.preview`.
"""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import sheet_preview
from .authority import space_for
from .serializers_history import SheetPreviewRequestSerializer, SheetPreviewSerializer
from .views_jobs import job_params, member_card_targets

TAGS = ["Card jobs"]
DESCRIPTION = ("Renders at most one sheet (front and mirrored back) at screen resolution and says how many sheets "
               "the real job prints. Nothing is queued or stored. Audited `card_job.previewed` (counts only); a "
               "superadmin needs a PII window.")


class MemberCardSheetPreviewView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "card_render"

    @extend_schema(tags=TAGS, summary="Preview the first print sheet of a member-card bulk job",
                   description=DESCRIPTION, request=SheetPreviewRequestSerializer,
                   responses={200: SheetPreviewSerializer, **errors(400, 401, 403, 404, 429)})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        data = SheetPreviewRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        return Response(sheet_preview.preview(request.user, space, "member_card", member_card_targets(space, values),
                                              job_params(values), scope="member_cards"))
