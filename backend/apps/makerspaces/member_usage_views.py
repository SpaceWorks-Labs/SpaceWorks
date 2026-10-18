"""The member usage boundary, with core money visibility independent of membership."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.member_activity_service import active_membership
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import servable_queryset
from apps.payments.member_access import member_may_see_own_charges
from .member_usage_serializers import MemberUsageSerializer
from .member_usage_service import member_usage, payment_usage


class MemberUsageView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MemberUsageSerializer
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        tags=["Member activity"], summary="Retrieve only the caller's personal usage charts",
        description=(
            "Non-payment usage requires an active membership and the membership module, "
            "like member activity. Otherwise eligible callers receive payments only. "
            "Payment totals follow member_may_see_own_charges and remain visible with "
            "membership and payment rail modules disabled. Revoked memberships are refused. "
            "All data is filtered by the authenticated user; no member id is accepted. "
            "Loan counts represent handovers, deduplicating direct loans' linked workflow "
            "requests; monthly returns count ReturnEvents by event time, including partial returns. "
            "Legacy direct returns without events use returned_at; quantities are not inferred. "
            "Machine hours are attributed MachineUsageEntry hours only; unknown historical "
            "attribution is excluded. Booking counts exclude cancelled reservations."
        ),
        request=None, responses={
            200: MemberUsageSerializer,
            401: OpenApiResponse(ErrorSerializer, description="Authentication required."),
            403: OpenApiResponse(ErrorSerializer, description="No active membership or own charge visibility."),
            404: OpenApiResponse(ErrorSerializer, description="Makerspace not found or not servable."),
        },
    )
    def get(self, request, makerspace_id):
        space = get_object_or_404(servable_queryset(), pk=makerspace_id)
        member = request.user
        membership = active_membership(member, space.pk)
        # The usage surface is not the narrow rejoining-admission payment exception.
        if membership is None and MakerspaceMembership.objects.filter(user=member, makerspace=space).exists():
            raise PermissionDenied()
        money_visible = member_may_see_own_charges(member, space.pk)
        if membership is None and not money_visible:
            raise PermissionDenied()
        usage_available = membership is not None and module_enabled(space, "membership")
        data = {"usage_available": usage_available}
        if usage_available:
            data.update(member_usage(space, member))
        if money_visible:
            data["payments"] = payment_usage(space, member)
        response = Response(MemberUsageSerializer(data).data)
        response["Cache-Control"] = "private, no-store"
        return response
