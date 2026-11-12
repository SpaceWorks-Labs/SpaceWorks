"""Batch print preview for staff ID cards (decision 344(b)): the first sheet before the bulk job is queued, exactly
like member, programme and event cards (`sheet_preview.preview`; audited `card_job.previewed`, counts only)."""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import sheet_preview
from .models_staff_cards import StaffCard
from .serializers_history import SheetPreviewRequestSerializer, SheetPreviewSerializer
from .staff_card_access import space_for
from .views_jobs import job_params
from .views_sheet_preview import DESCRIPTION


class StaffCardSheetPreviewView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "card_render"

    @extend_schema(tags=["Staff ID cards"], summary="Preview the first print sheet of a staff-card bulk job",
                   description=DESCRIPTION, request=SheetPreviewRequestSerializer,
                   responses={200: SheetPreviewSerializer, **errors(400, 401, 403, 404, 429)})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        data = SheetPreviewRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        # The same targets as the staff-card job: active cards of current staff, by card number.
        rows = StaffCard.objects.filter(makerspace=space, revoked_at__isnull=True, membership__isnull=False)
        if values.get("card_ids"):
            rows = rows.filter(pk__in=values["card_ids"])
        targets = list(rows.order_by("card_number").values_list("pk", flat=True))
        return Response(sheet_preview.preview(request.user, space, "staff_card", targets, job_params(values),
                                              scope="staff_cards"))
