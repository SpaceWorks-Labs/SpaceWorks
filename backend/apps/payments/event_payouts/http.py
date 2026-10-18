"""Always-mounted private HTTP helpers, independent of Events permissions."""
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from .authority import authorize
from .errors import require, PayoutError
from .obligation_models import EventPayoutObligation
from .validation import PayoutValidationError
from apps.tenant_migration.gate_runtime import assert_write_allowed
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import NotFound


class PrivateView(APIView):
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        if isinstance(exc, ObjectDoesNotExist):
            exc = NotFound()
        elif isinstance(exc, PayoutValidationError):
            exc = PayoutError(exc.code, status=400)
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        return response


def body(request, serializer):
    value = serializer(data=request.data)
    value.is_valid(raise_exception=True)
    require(request.headers.get("Idempotency-Key") == str(value.validated_data["operation_id"]),
            "idempotency_key_mismatch", status=400)
    return value.validated_data


def obligation(request, obligation_id, *, makerspace_id=None, owner=False):
    rows = EventPayoutObligation.objects.select_related("makerspace", "current_revision")
    if owner:
        rows = rows.filter(owner_member=request.user)
    if makerspace_id is not None:
        rows = rows.filter(makerspace_id=makerspace_id)
    row = get_object_or_404(rows, pk=obligation_id)
    authorize(request, row.makerspace, owner=owner, owner_id=row.owner_member_id)
    assert_write_allowed(row.makerspace_id)
    return row


def paginate(request, rows, project):
    pager = PageNumberPagination()
    pager.page_size = 24
    page = pager.paginate_queryset(rows, request)
    return pager.get_paginated_response([project(row) for row in page])
