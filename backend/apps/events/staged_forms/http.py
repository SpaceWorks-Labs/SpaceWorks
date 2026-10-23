"""Shared authenticated, private stage HTTP boundary; no implicit creation on GET."""
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from apps.accounts.account_kind_guards import require_member_account
from apps.events.models import Event
from apps.makerspaces.guards import require_module
from apps.payments.event_payouts.errors import require
from apps.presence.guard import require_active_principal
from apps.tenant_migration.gate_runtime import assert_write_allowed
from django.core.exceptions import ObjectDoesNotExist, ValidationError as ModelValidationError
from rest_framework.exceptions import NotFound, ValidationError
from apps.payments.event_payouts.errors import PayoutError
from apps.payments.event_payouts.validation import PayoutValidationError
from .policy import StagePolicyError


class PrivateView(APIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        from apps.accounts.claim_sessions import claim_context
        require(getattr(request, "api_client", None) is None and claim_context(request.user) is None,
                "full_session_required", status=403)

    def handle_exception(self, exc):
        from apps.makerspaces.private_upload_transport import PrivateTransportError
        if isinstance(exc, PrivateTransportError):
            exc = PayoutError(exc.code, status=exc.status)
        elif isinstance(exc, ObjectDoesNotExist):
            exc = NotFound()
        elif isinstance(exc, (StagePolicyError, PayoutValidationError)):
            exc = PayoutError(exc.code, status=400)
        elif isinstance(exc, ModelValidationError):
            exc = PayoutError(getattr(exc, "code", None) or "invalid_stage_configuration", status=400)
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        response["Vary"] = "Authorization, Cookie"
        return response


def body(request, serializer_class):
    value = serializer_class(data=request.data)
    value.is_valid(raise_exception=True)
    require(request.headers.get("Idempotency-Key") == str(value.validated_data["operation_id"]),
            "idempotency_key_mismatch", status=400)
    return value.validated_data


def member_event(request, pk, makerspace_id):
    from apps.accounts.claim_sessions import claim_context
    from apps.makerspaces.models import MakerspaceMembership
    require_member_account(request.user)
    event = get_object_or_404(Event.objects.select_related("makerspace"), pk=pk, makerspace_id=makerspace_id)
    require_module(event.makerspace, "events")
    require_active_principal(request.user, event.makerspace)
    require(claim_context(request.user) is None, "full_session_required", status=403)
    require(not MakerspaceMembership.objects.filter(user=request.user, makerspace=event.makerspace).exclude(status="active").exists(),
            "account_restricted", status=403)
    assert_write_allowed(event.makerspace_id)
    return event


def staff_event(request, pk, permission):
    from apps.events import event_authority
    event = event_authority.get_event(request.user, pk, permission)
    assert_write_allowed(event.makerspace_id)
    return event


def paginated(request, rows, project):
    pager = PageNumberPagination()
    pager.page_size = 24
    page = pager.paginate_queryset(rows, request)
    return pager.get_paginated_response([project(row) for row in page])
