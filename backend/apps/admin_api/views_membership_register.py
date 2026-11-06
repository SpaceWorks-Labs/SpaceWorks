"""The member register with standing filters (X14). Its CSV export is the
`member-register` report (report registry: manage_members, audited, PII rules).

Standings: active, ending_soon (ends within 30 days), grace, lapsed, upcoming, no_term.
A superadmin without an open PII window sees masked names and emails.
"""
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.pii_presentation import MASK, pii_visible
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_membership_l4_common import staff_space
from apps.admin_api.views_roles import ERRORS

STANDINGS = ("active", "ending_soon", "grace", "lapsed", "upcoming", "no_term")
_ROW = inline_serializer("MemberRegisterRow", {
    "member_number": serializers.CharField(), "name": serializers.CharField(), "email": serializers.CharField(),
    "plan": serializers.CharField(), "standing": serializers.CharField(),
    "term_ends_at": serializers.DateTimeField(allow_null=True), "source": serializers.CharField(),
    "joined_at": serializers.DateTimeField()})


class MemberRegisterView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin memberships"], summary="The member register, filtered by standing",
                   description="Requires manage_members and membership.register_tools. Up to 2000 rows; the "
                               "full file is the member-register report export.",
                   parameters=[OpenApiParameter("standing", str, enum=STANDINGS, required=False)],
                   responses={200: _ROW, **ERRORS})
    def get(self, request, makerspace_id):
        from apps.operations.reports_membership_l4_lists import build_member_register
        space = staff_space(request.user, makerspace_id, "register_tools")
        standing = request.query_params.get("standing") or None
        if standing is not None and standing not in STANDINGS:
            raise ValidationError({"standing": gettext('Use one of: {value}.').format(value=', '.join(STANDINGS))})
        rows = build_member_register(space.pk, limit=2000, standing=standing).records
        if not pii_visible(request.user, space.pk):
            rows = [{**row, "name": MASK, "email": MASK, "pii_masked": True} for row in rows]
        return Response(rows)
