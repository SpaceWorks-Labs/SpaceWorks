"""Decision 223: the Space Manager's guest-pass policy and day-pass products (manage_makerspace, audited).

Both are per-makerspace settings with the defaults the owner chose (on-site borrowing, no machine
use, the guest accountable, walk-ins become guest passes, a waiver required, sponsors need 30 days
and may bring 2 guests, a join prompt after 4 visits in 30 days). A policy edit never rewrites a
live pass: its entitlements were frozen when it was issued.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_member_memberships import _makerspace
from apps.admin_api.views_membership_l4_common import staff_space
from apps.makerspaces.platform import module_enabled
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import guest_pass_day, guest_pass_policy
from apps.makerspaces.models import DayPassProduct
from apps.makerspaces.serializers_guest_passes import DayPassProductSerializer, GuestPassPolicySerializer

TAG = "Admin guest passes"
MANAGE = rbac.Action.MANAGE_MAKERSPACE


WAIVER_ONLY_FIELDS = frozenset({"waiver_required_on_site", "waiver_gate_without_passes"})


def _policy_space(user, makerspace_id):
    """Guest passes on: the full policy. Off but presence or membership on: the waiver gate alone (EV-25)."""
    space = _makerspace(user, makerspace_id, MANAGE)
    if guest_pass_policy.guest_passes_on(space):
        return space, False
    if module_enabled(space, "presence") or module_enabled(space, "membership"):
        return space, True
    return staff_space(user, makerspace_id, "guest_passes", MANAGE), False  # raises the typed 404


class GuestPassPolicyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Read the guest-pass policy",
                   description="Requires manage_makerspace and either membership.guest_passes or the presence / "
                               "membership module (the on-site waiver gate lives here too). A space that never "
                               "saved the policy returns the defaults.",
                   responses={200: GuestPassPolicySerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space, _ = _policy_space(request.user, makerspace_id)
        return Response(GuestPassPolicySerializer(guest_pass_policy.policy_for(space)).data)

    @extend_schema(tags=[TAG], summary="Change the guest-pass policy",
                   description="Partial update. Audited with the names of the changed settings. Live passes "
                               "keep the entitlements they were issued with. While guest passes are off, only "
                               "`waiver_required_on_site` and `waiver_gate_without_passes` may be sent (400 "
                               "otherwise).",
                   request=GuestPassPolicySerializer(partial=True), responses={200: GuestPassPolicySerializer, **ERRORS})
    def patch(self, request, makerspace_id):
        space, waiver_only = _policy_space(request.user, makerspace_id)
        if waiver_only:
            extra = sorted(set(request.data) - WAIVER_ONLY_FIELDS)
            if extra:
                raise ValidationError({name: "Only the waiver gate can change while guest passes are off."
                                       for name in extra})
        data = GuestPassPolicySerializer(guest_pass_policy.policy_for(space), data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return Response(GuestPassPolicySerializer(
            guest_pass_policy.update_policy(request.user, space, dict(data.validated_data))).data)


class DayPassProductListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="List the day-pass products",
                   description="Requires manage_makerspace and membership.day_passes. Archived products are "
                               "listed last with `archived_at` set.",
                   responses={200: DayPassProductSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "day_passes", MANAGE)
        rows = DayPassProduct.objects.filter(makerspace=space).order_by("archived_at", "name", "pk")
        return Response(DayPassProductSerializer(rows, many=True).data)

    @extend_schema(tags=[TAG], summary="Create a day-pass product",
                   description="A product with a price needs `charges.membership` on; a free product does not.",
                   request=DayPassProductSerializer, responses={201: DayPassProductSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "day_passes", MANAGE)
        data = DayPassProductSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(DayPassProductSerializer(
            guest_pass_day.save_product(request.user, space, dict(data.validated_data))).data,
            status=status.HTTP_201_CREATED)


class DayPassProductDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Edit a day-pass product",
                   request=DayPassProductSerializer(partial=True), responses={200: DayPassProductSerializer, **ERRORS})
    def patch(self, request, makerspace_id, product_id):
        space = staff_space(request.user, makerspace_id, "day_passes", MANAGE)
        product = get_object_or_404(DayPassProduct, pk=product_id, makerspace=space)
        data = DayPassProductSerializer(product, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return Response(DayPassProductSerializer(
            guest_pass_day.save_product(request.user, space, dict(data.validated_data), product)).data)


class DayPassProductArchiveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Archive a day-pass product",
                   description="Archived, never deleted: sold passes keep pointing at it.",
                   request=None, responses={200: DayPassProductSerializer, **ERRORS})
    def post(self, request, makerspace_id, product_id):
        space = staff_space(request.user, makerspace_id, "day_passes", MANAGE)
        product = get_object_or_404(DayPassProduct, pk=product_id, makerspace=space)
        return Response(DayPassProductSerializer(guest_pass_day.archive_product(request.user, product)).data)
