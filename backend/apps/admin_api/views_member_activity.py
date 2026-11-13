"""Decision 242(e): GET the staff member 360 for one member of a space."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.member_activity import build_member_activity
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.servability import servable_queryset


class _LinkSerializer(serializers.Serializer):
    tab = serializers.CharField()
    filters = serializers.DictField(child=serializers.CharField())


class _RowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    status = serializers.CharField()
    at = serializers.DateTimeField(allow_null=True)
    link = _LinkSerializer()


class MemberActivityAreaSerializer(serializers.Serializer):
    area = serializers.ChoiceField(choices=["lending", "bookings", "machines", "events", "shop", "money", "safety", "people"])
    count = serializers.IntegerField(help_text="Every row of this member in the area, whoever the viewer is.")
    rows_visible = serializers.BooleanField(help_text="False: the viewer does not manage this area, counts only.")
    rows = _RowSerializer(many=True, allow_null=True)
    open = serializers.IntegerField(required=False)
    pending = serializers.IntegerField(required=False)
    owed = serializers.DictField(child=serializers.CharField(), required=False)
    guest_passes = serializers.IntegerField(required=False)
    volunteer_entries = serializers.IntegerField(required=False)
    certifications = serializers.IntegerField(required=False)


class MemberActivitySerializer(serializers.Serializer):
    class Meta:
        ref_name = "StaffMemberActivity"

    member_id = serializers.IntegerField()
    areas = MemberActivityAreaSerializer(many=True)
    errors = serializers.ListField(child=serializers.CharField())
    # Open item A26: the borrower drawer shows restriction state beside loans and charges.
    access_status = serializers.ChoiceField(choices=["active", "restricted", "suspended"], required=False)
    is_member = serializers.BooleanField(required=False, help_text="False for an account-only borrower of this space.")


# Decision 248: counts open to every staff role holding any area action in the space; the builders still
# narrow ROWS to the areas the viewer manages. Handover-only desks and plain members hold none of these.
_AREA_ACTIONS = (
    rbac.Action.MANAGE_MEMBERS, rbac.Action.MANAGE_EVENTS, rbac.Action.MANAGE_BOOKINGS, rbac.Action.MANAGE_MACHINES,
    rbac.Action.MANAGE_SHOP, rbac.Action.VIEW_SHOP, rbac.Action.VIEW_INVENTORY, rbac.Action.ACCEPT_REQUEST,
    rbac.Action.WORK_REPAIRS, rbac.Action.RUN_MAINTENANCE, rbac.Action.SET_SERVICE_STATE,
    rbac.Action.VIEW_FINANCE, rbac.Action.RECORD_PAYMENT,
)


def _holds_area_action(actor, space_id):
    if rbac.is_handout_only(actor, space_id):
        return False
    return any(rbac.can(actor, action, space_id) for action in _AREA_ACTIONS)


class MemberActivityView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin members"], summary="One member's activity across every area (member 360)",
        # A26: also answers for an account-only borrower who has a loan request in this space.
        description=("Any staff role holding an area action in the space (not handover-only desks). Counts and links for every area; rows only for areas the viewer "
                     "manages (the Space Manager sees all). Decision 242(e)."),
        responses={200: MemberActivitySerializer, 401: OpenApiResponse(ErrorSerializer),
                   403: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer)},
    )
    def get(self, request, makerspace_id, user_id):
        space = get_object_or_404(servable_queryset(), pk=makerspace_id)
        if not _holds_area_action(request.user, space.pk):
            raise NotFound()
        membership = MakerspaceMembership.objects.select_related("user").filter(
            makerspace=space, user_id=user_id).first()
        user = membership.user if membership else _account_only_borrower(space, user_id)
        data = build_member_activity(request.user, space, user)
        return Response({**data, "access_status": user.access_status, "is_member": membership is not None})


def _account_only_borrower(space, user_id):
    """Open item A26: an account-only borrower (no membership) who has borrowed in this space; else 404."""
    from apps.hardware_requests.models import HardwareRequest

    request_row = HardwareRequest.objects.select_related("requester").filter(
        makerspace=space, requester_id=user_id).first()
    if request_row is None:
        raise NotFound()
    return request_row.requester
