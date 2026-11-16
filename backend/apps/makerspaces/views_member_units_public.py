"""Parity O-B1: the public unit picker on the join page (`GET public/<slug>/member-units?code=`).

Only unit names, codes and levels are returned -- no members, counts, payment instructions or archived units.
It 404s when the module or `membership.units` is off, so a space that does not use units shows no picker.
With `?code=` it also resolves that one unit (the `?unit=CODE` link) and the plans offered in it.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces import member_units
from apps.makerspaces.guards import require_module
from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.membership_join_units import plans_for_unit, unit_by_code
from apps.makerspaces.models import MembershipPlan
from apps.makerspaces.servability import servable_queryset

class PublicMemberUnitSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    level = serializers.IntegerField()
    level_name = serializers.CharField()
    parent_code = serializers.CharField(allow_null=True)


_RESPONSE = inline_serializer("PublicMemberUnits", {
    "levels": serializers.ListField(child=serializers.CharField()), "units": PublicMemberUnitSerializer(many=True),
    "selected": PublicMemberUnitSerializer(allow_null=True),
    "plan_ids": serializers.ListField(child=serializers.IntegerField(), allow_null=True,
                                      help_text="With `code`: the active plans offered in that unit.")})


class PublicMemberUnitsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(auth=[], tags=["Memberships"], summary="The unit picker for the join page",
                   parameters=[OpenApiParameter("code", str, required=False)],
                   responses={200: _RESPONSE, 404: ErrorSerializer})
    def get(self, request, makerspace_slug):
        space = get_object_or_404(servable_queryset(), slug=makerspace_slug)
        require_module(space, "membership")
        require_membership_feature(space, "units")
        rows = member_units.tree(space)
        by_id = {row["id"]: row for row in rows}
        units = [{"code": row["code"], "name": row["name"], "level": row["level"], "level_name": row["level_name"],
                  "parent_code": by_id[row["parent_id"]]["code"] if row["parent_id"] in by_id else None}
                 for row in rows]
        unit = unit_by_code(space, request.query_params.get("code"))
        selected = next((row for row in units if unit and row["code"] == unit.code), None)
        plan_ids = None
        if unit is not None:
            plans = MembershipPlan.objects.filter(makerspace=space, is_active=True, archived_at__isnull=True)
            plan_ids = sorted(plans_for_unit(plans, unit).values_list("pk", flat=True))
        return Response({"levels": member_units.level_names(space), "units": units, "selected": selected,
                         "plan_ids": plan_ids})
