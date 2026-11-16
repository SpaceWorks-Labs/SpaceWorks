"""Contextual equipment request surfaces (private candidate; orchestration pending)."""
from django.shortcuts import get_object_or_404
from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.hardware_requests.contextual_equipment_serializers import (
    ContextualSelfResultSerializer, ContextualSelfSerializer,
    ContextualStaffResultSerializer, ContextualStaffSerializer,
)
from apps.hardware_requests.contextual_equipment_service import ProposalConflict, create_pending
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.public_request_views import _honeypot_filled, _honeypot_response
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.guards import require_module_for_servable
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.request_access import require_current_term
from apps.hardware_requests.guest_lending import admit_borrower
from apps.presence.guard import require_active_account


class Conflict(APIException):
    status_code = 409
    default_code = "operation_conflict"
    default_detail = "The operation cannot be completed."


class IntakeUnavailable(APIException):
    status_code = 503
    default_code = "intake_unavailable"
    default_detail = "Equipment proposals are temporarily unavailable."


def _fields(data):
    keys = ("items", "kit", "requested_for", "pickup_from", "pickup_until", "waitlist_entry_id")
    result = {key: data[key] for key in keys if key in data}
    for key in ("pickup_from", "pickup_until"):
        if result.get(key) is not None:
            result[key] = result[key].isoformat()
    return result


def _submit(*, maker, actor, borrower, kind, data):
    try:
        outcome, result, replayed = create_pending(
            makerspace_id=maker.pk, actor=actor, borrower=borrower, intent_kind=kind,
            operation_id=data["operation_id"], event_registration_id=data["event_registration_id"],
            booking_id=data.get("booking_id"), booking_token=data.get("booking_token"),
            borrower_id=data.get("borrower_id"), items=data.get("items"), kit=data.get("kit"), requested_for=data["requested_for"],
            pickup_from=data["pickup_from"], pickup_until=data["pickup_until"],
            waitlist_entry_id=data["waitlist_entry_id"], canonical_fields=_fields(data),
        )
    except ProposalConflict as exc:
        error = Conflict()
        error.detail = {"code": str(exc), "detail": error.default_detail}
        raise error from exc
    return outcome, result, replayed


class ContextualSelfView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    @extend_schema(request=ContextualSelfSerializer, responses={
        200: ContextualSelfResultSerializer, 201: ContextualSelfResultSerializer,
        400: OpenApiResponse(description="Invalid request."),
        401: OpenApiResponse(description="Authentication required."),
        403: OpenApiResponse(ErrorSerializer, description="Account, membership, waiver or presence requirements are not met."),
        404: OpenApiResponse(description="Target unavailable."),
        409: OpenApiResponse(ErrorSerializer, description="Operation conflict or lock busy."),
        423: OpenApiResponse(ErrorSerializer, description="Tenant frozen."),
        429: OpenApiResponse(description="Member request rate limit exceeded."),
        503: OpenApiResponse(description="Intake unavailable."),
    })
    def post(self, request, makerspace_slug):
        maker = get_public_makerspace(makerspace_slug)
        if not maker.public_site_enabled or not maker.public_inventory_enabled:
            raise Http404
        require_module_for_servable(maker, "public_inventory")
        if _honeypot_filled(request.data):
            if module_enabled(maker, "membership"):
                admit_borrower(maker, request.user, planning=True)  # planning: no presence (decision 223)
            else:
                require_active_account(request.user, maker)
            decoy = _honeypot_response()
            decoy.data.update(kind="request", replayed=False)
            return decoy
        serializer = ContextualSelfSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        outcome, result, replayed = _submit(maker=maker, actor=request.user, borrower=request.user,
                                            kind="self", data=data)
        body = {"kind": outcome, "replayed": replayed}
        if outcome == "request":
            body.update(public_token=result.public_token, status=result.status)
        else:
            body["plan_id"] = result.pk
        return Response(body, status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED)


class ContextualStaffView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsAuthenticated, IsActiveStaff]

    @extend_schema(request=ContextualStaffSerializer, responses={
        200: ContextualStaffResultSerializer, 201: ContextualStaffResultSerializer,
        400: OpenApiResponse(description="Invalid request."),
        401: OpenApiResponse(description="Authentication required."),
        403: OpenApiResponse(description="Staff authority required."),
        404: OpenApiResponse(description="Target unavailable."),
        409: OpenApiResponse(ErrorSerializer, description="Operation conflict or lock busy."),
        423: OpenApiResponse(ErrorSerializer, description="Tenant frozen."),
        503: OpenApiResponse(description="Intake unavailable."),
    })
    def post(self, request, makerspace_id):
        from apps.makerspaces.models import Makerspace
        maker = get_object_or_404(Makerspace, pk=makerspace_id)
        serializer = ContextualStaffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        outcome, result, replayed = _submit(maker=maker, actor=request.user, borrower=None,
                                            kind="staff", data=data)
        body = {"kind": outcome, "replayed": replayed}
        if outcome == "request":
            body.update(request_id=result.pk, status=result.status)
        else:
            body["plan_id"] = result.pk
        return Response(body, status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED)
