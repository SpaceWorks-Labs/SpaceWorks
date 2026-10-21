"""Per-area cancellation refund policy. Core ledger; editing needs manage_makerspace."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.servability import servable_queryset
from apps.payments.models import MakerspacePaymentSettings, RefundPolicy
from apps.payments.serializers_refund_cases import RefundPolicySerializer

ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (400, 401, 403, 404)}
#: Who may READ the policy: the people who decide cases under it, and finance.
READ_ACTIONS = (rbac.Action.MANAGE_MAKERSPACE, rbac.Action.VIEW_FINANCE,
                rbac.Action.MANAGE_EVENTS, rbac.Action.MANAGE_BOOKINGS)


def _space(actor, makerspace_id, actions):
    for action in actions:
        space = rbac.scope_by_action(actor, action, servable_queryset(), field="pk").filter(pk=makerspace_id).first()
        if space is not None:
            return space
    raise NotFound("Makerspace not found.")


def _area(area):
    if area not in RefundPolicy.Area.values:
        raise NotFound("Unknown refund policy area.")
    return area


def _context(space):
    return {"currency": MakerspacePaymentSettings.for_makerspace(space).default_currency}


class RefundPolicyListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Payments"], summary="Read the refund policy for every area",
        description="Requires manage_makerspace, view_finance, manage_events or manage_bookings. One row per "
                    "area (events, bookings); `configured=false` means no policy -- a cancellation owes nothing "
                    "automatically and staff decide each request. A space-cancelled event is always owed in full.",
        request=None, responses={200: RefundPolicySerializer(many=True), **ERRORS},
    )
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id, READ_ACTIONS)
        rows = {row.area: row for row in RefundPolicy.objects.filter(makerspace=space)}
        policies = [rows.get(area) or RefundPolicy(makerspace=space, area=area) for area in RefundPolicy.Area.values]
        return Response(RefundPolicySerializer(policies, many=True, context=_context(space)).data)


class RefundPolicyDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Payments"], summary="Set the refund policy for one area",
        description="Requires manage_makerspace. Cancelling at least `full_before_minutes` before the start "
                    "refunds in full; at least `partial_before_minutes` refunds `partial_percent`; later refunds "
                    "nothing. `cancellation_fee` (space currency) is kept from any refund. Applies to future "
                    "cancellations only. Audited.",
        request=RefundPolicySerializer, responses={200: RefundPolicySerializer, **ERRORS},
    )
    @transaction.atomic
    def put(self, request, makerspace_id, area):
        space = _space(request.user, makerspace_id, (rbac.Action.MANAGE_MAKERSPACE,))
        area = _area(area)
        space = servable_queryset().select_for_update().get(pk=space.pk)
        policy = RefundPolicy.objects.filter(makerspace=space, area=area).first() or RefundPolicy(
            makerspace=space, area=area)
        serializer = RefundPolicySerializer(policy, data=request.data, context=_context(space))
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        audit.record(request.user, "payment.refund_policy_updated", makerspace=space, target=space,
                     meta={"area": area, "fields": sorted(serializer.validated_data)})
        return Response(serializer.data)

    @extend_schema(
        tags=["Payments"], summary="Remove the refund policy for one area",
        description="Requires manage_makerspace. Afterwards a cancellation owes nothing automatically and staff "
                    "decide each request. Open cases keep the figure they were assessed with. Audited.",
        request=None, responses={204: None, **ERRORS},
    )
    @transaction.atomic
    def delete(self, request, makerspace_id, area):
        space = _space(request.user, makerspace_id, (rbac.Action.MANAGE_MAKERSPACE,))
        policy = get_object_or_404(RefundPolicy.objects.select_for_update(), makerspace=space, area=_area(area))
        policy.delete()
        audit.record(request.user, "payment.refund_policy_updated", makerspace=space, target=space,
                     meta={"area": area, "removed": True})
        return Response(status=204)
