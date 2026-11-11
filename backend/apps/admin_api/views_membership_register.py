"""The member register with standing filters (X14). Its CSV export is the
`member-register` report (report registry: manage_members, audited, PII rules).

Standings: active, ending_soon (ends within 30 days), grace, lapsed, upcoming, no_term.
Parity O-B2: the register takes the shared filter contract of `member_register_filters` (`q` incl. member number,
`chip`, `plan`, `title`, `unit`, ...), the same one the roster and bulk card jobs use; a unit-scoped actor only
ever sees the members of their unit.
A superadmin without an open PII window sees masked names and emails.
"""
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.pii_presentation import MASK, pii_visible
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_membership_l4_common import staff_space
from apps.admin_api.views_roles import ERRORS

STANDINGS = ("active", "ending_soon", "grace", "lapsed", "upcoming", "no_term")
_ROW = inline_serializer("MemberRegisterRow", {
    "membership_id": serializers.IntegerField(), "unit": serializers.CharField(allow_null=True),
    "member_number": serializers.CharField(), "name": serializers.CharField(), "email": serializers.CharField(),
    "plan": serializers.CharField(), "standing": serializers.CharField(),
    "term_ends_at": serializers.DateTimeField(allow_null=True), "source": serializers.CharField(),
    "joined_at": serializers.DateTimeField()})


class MemberRegisterView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin memberships"], summary="The member register, filtered",
                   description="Requires manage_members and membership.register_tools. Up to 2000 rows; the "
                               "full file is the member-register report export. Filters: the shared member "
                               "filter contract (see `member_register_filters`); `standing` still accepts the "
                               "term standings.",
                   parameters=[OpenApiParameter("standing", str, enum=STANDINGS, required=False),
                               OpenApiParameter("chip", str, required=False),
                               OpenApiParameter("q", str, required=False, description="Name, email or member number."),
                               OpenApiParameter("plan", int, required=False), OpenApiParameter("title", int, required=False),
                               OpenApiParameter("unit", int, required=False)],
                   responses={200: _ROW(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        from apps.admin_api.member_register_filters import apply_member_filters, register_params
        from apps.makerspaces.models import MakerspaceMembership
        from apps.makerspaces.models_member_units import MembershipUnit
        from apps.operations.reports_membership_l4_lists import build_member_register
        space = staff_space(request.user, makerspace_id, "register_tools")
        params = register_params(request.query_params)
        members = apply_member_filters(MakerspaceMembership.objects.filter(makerspace=space), params, space,
                                       actor=request.user, action=rbac.Action.MANAGE_MEMBERS)
        rows = build_member_register(space.pk, limit=2000, member_ids=list(members.values_list("pk", flat=True))).records
        units = dict(MembershipUnit.objects.filter(membership_id__in=[row["membership_id"] for row in rows])
                     .values_list("membership_id", "unit__code"))
        rows = [{**row, "unit": units.get(row["membership_id"])} for row in rows]
        if not pii_visible(request.user, space.pk):
            rows = [{**row, "name": MASK, "email": MASK, "pii_masked": True} for row in rows]
        return Response(rows)
