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
from apps.makerspaces.private_upload_transport import PrivateTransportError
from apps.encryption.crypto import PiiUnavailable
from .attachment_content import ContentError
from django.db import IntegrityError


class PrivateView(APIView):
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        if isinstance(exc, ObjectDoesNotExist):
            exc = NotFound()
        elif isinstance(exc, PayoutValidationError):
            exc = PayoutError(exc.code, status=400)
        elif isinstance(exc, (PrivateTransportError, ContentError)):
            exc = PayoutError(exc.code, status=exc.status)
        elif isinstance(exc, PiiUnavailable):
            exc = PayoutError(getattr(exc, "code", "finance_data_unavailable"), status=getattr(exc, "status_code", 503))
        elif isinstance(exc, IntegrityError):
            cause = exc.__cause__
            if getattr(cause, "sqlstate", None) == "23505":
                constraint = getattr(getattr(cause, "diag", None), "constraint_name", "") or ""
                # A UUID collision across different locked hosts/obligations can
                # reach the unique backstop. Never echo a constraint/SQL value.
                exc = PayoutError("idempotency_conflict" if "operation_id" in constraint else "finance_conflict")
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
