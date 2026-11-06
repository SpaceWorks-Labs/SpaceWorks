"""Owner self-service for machine-service jobs on the MEMBER surface (C4).

Both routes act only on the caller's OWN job (``member_id == caller``), need a live
member account and a servable tenant, and work with the ``membership`` module off --
an account-only borrower can stop their own job with no presence/waiver prerequisite.
A bearer tracking token alone never authorizes a write: the by-token lookup resolves the
token AND proves ownership before returning the private ``request_id``. Claim sessions,
staff and platform accounts are refused. Staff cancellation stays on the admin route.
"""

from decimal import Decimal

from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.account_kind_guards import require_member_account
from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.machines import service_workflow
from apps.machines.models import MachineServiceRequest
from apps.machines.public_printer_service import _StatusProjection, status_context
from apps.machines.public_service_serializers import PublicMachineServiceStatusSerializer
from apps.machines.service_workflow_cancel import owner_may_cancel
from apps.makerspaces.servability import servable_queryset

OWNER_ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid input."),
    401: OpenApiResponse(description="Authentication required."),
    403: OpenApiResponse(ErrorSerializer, description="A live member account is required; claim, staff and platform sessions are refused."),
    404: OpenApiResponse(description="No job owned by the caller matches, or machine service is off for this makerspace."),
    409: OpenApiResponse(ErrorSerializer, description="The job is already terminal and cannot be cancelled."),
    429: OpenApiResponse(ErrorSerializer, description="Rate limit exceeded."),
}


class MemberServiceCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500, trim_whitespace=True)
    consumed_quantity = serializers.DecimalField(
        required=False, allow_null=True, max_digits=12, decimal_places=2, min_value=Decimal("0"),
        help_text=("Material used so far by a RUNNING job, in its consumable hold's unit (0 to the held "
                   "amount). It stays taken from stock and is costed; nothing is charged. Empty or 0 "
                   "releases the whole hold."),
    )


class MemberServiceOwnerSerializer(serializers.Serializer):
    request_id = serializers.IntegerField()
    can_cancel = serializers.BooleanField()


def _require_owner_session(request):
    if getattr(request, "claim_session", None) is not None:
        raise PermissionDenied("Claim sessions cannot manage machine-service jobs.")
    user = request.user
    require_member_account(user)
    if not (user.is_active and user.access_status == "active"):
        raise PermissionDenied("An active member account is required.")
    return user


def _owned(user, query):
    """The caller's own job in a servable tenant, or 404 (never discloses other jobs)."""
    row = servable_queryset(MachineServiceRequest.objects.select_related(
        "makerspace", "queue__machine_type", "bucket__machine__machine_type",
    ).filter(query, member_id=user.pk), relation="makerspace").first()
    if row is None:
        raise NotFound()
    return row


class MemberMachineServiceCancelView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    @extend_schema(
        tags=["Member machine service"], summary="Cancel your own machine-service job",
        description=("Owner-only. A job can be cancelled until staff start it (submitted, needs changes, "
                     "quoted or queued); a running job is the staff's to stop (403). Any held consumables "
                     "are released with no charge. Repeating a successful cancel returns the same result."),
        request=MemberServiceCancelSerializer,
        responses={200: PublicMachineServiceStatusSerializer, **OWNER_ERRORS},
    )
    def post(self, request, pk):
        user = _require_owner_session(request)
        row = _owned(user, Q(pk=pk))
        serializer = MemberServiceCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        row = service_workflow.cancel(row, user, reason=data.get("reason", ""), by_owner=True,
                                      consumed_quantity=data.get("consumed_quantity"))
        row = _owned(user, Q(pk=row.pk))
        projection = _StatusProjection(row, printer=False)
        projection.machine_type_name = (row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type).name
        # A fresh snapshot built AFTER the mutation: never a pre-cancel cache.
        return Response(PublicMachineServiceStatusSerializer(projection, context=status_context([row])).data)


class MemberMachineServiceOwnerView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "request_status"

    @extend_schema(
        tags=["Member machine service"], summary="Owner controls for a tracked machine-service job",
        description=("Resolves a tracking token for its OWNER only and returns the private request id and "
                     "whether it can still be cancelled. Non-owners and unknown tokens get 404. Not cached."),
        request=None, responses={200: MemberServiceOwnerSerializer, **OWNER_ERRORS},
    )
    def get(self, request, public_token):
        user = _require_owner_session(request)
        row = _owned(user, Q(public_token=public_token))
        response = Response(MemberServiceOwnerSerializer(
            {"request_id": row.pk, "can_cancel": owner_may_cancel(row, user)}).data)
        response["Cache-Control"] = "no-store"
        return response
