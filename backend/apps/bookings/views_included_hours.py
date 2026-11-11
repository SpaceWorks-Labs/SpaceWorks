"""Staff read of one member's included plan hours (open item C26).

Until now the balance was visible only inside the quote preview. This is the read-only line the
Member 360 / membership panel shows: per current term, the pool (room or machine), allowance, used
and remaining minutes -- exactly `included_hours.member_balances`, the same source the quote reads,
so the panel can never disagree with a price. Nothing is written, so there is no audit row; the
member's balance is read only by staff who may manage members or bookings in that space.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.servability import servable_queryset

from .included_hours_ledger import applies, member_balances


class IncludedHoursPoolSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["booking", "machine"])
    term_id = serializers.IntegerField()
    plan_name = serializers.CharField()
    term_starts_at = serializers.CharField()
    term_ends_at = serializers.CharField()
    allowance_minutes = serializers.IntegerField()
    used_minutes = serializers.IntegerField()
    remaining_minutes = serializers.IntegerField()


class MemberIncludedHoursSerializer(serializers.Serializer):
    class Meta:
        ref_name = "StaffMemberIncludedHours"

    member_id = serializers.IntegerField()
    enabled = serializers.BooleanField(help_text="False while membership or bookings is off: nothing is included.")
    pools = IncludedHoursPoolSerializer(many=True)


class MemberIncludedHoursView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin bookings"], summary="A member's included plan hours (current terms)",
        description=("Requires manage_members or manage_bookings in the space. A foreign space, or a person who "
                     "is not a member of it, reads as not found."),
        responses={200: MemberIncludedHoursSerializer, 401: OpenApiResponse(ErrorSerializer),
                   403: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer)},
    )
    def get(self, request, makerspace_id, user_id):
        allowed = rbac.makerspaces_for_actions(request.user, rbac.Action.MANAGE_MEMBERS, rbac.Action.MANAGE_BOOKINGS)
        if allowed is not rbac.ALL and makerspace_id not in allowed:
            raise NotFound()
        space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
        membership = MakerspaceMembership.objects.filter(
            makerspace=space, user_id=user_id).select_related("user").first()
        if membership is None:
            raise NotFound()
        enabled = applies(space)
        pools = member_balances(space, membership.user) if enabled else []
        return Response(MemberIncludedHoursSerializer(
            {"member_id": membership.user_id, "enabled": enabled, "pools": pools}).data)
