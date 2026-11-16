"""``GET admin/makerspace/<id>/allowances`` -- the limits a staff member manages, with what is left.

#234 addendum 3(a) + #224: the Space Manager sees every limited row; an area manager only the
rows of the areas they hold (``limits_role.AREAS``). Always 200 for a staff member of the space:
an empty ``rows`` list (hosting off, nothing limited) simply renders nothing.
"""

from django.http import Http404
from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors

from .limits_role import AREA_NAMES, allowance_rows


class StaffAllowanceRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.ChoiceField(choices=["bytes", "count"])
    limit = serializers.IntegerField()
    used = serializers.IntegerField(allow_null=True, help_text="Null for a per-file cap (nothing to count).")
    remaining = serializers.IntegerField(allow_null=True)
    percent = serializers.FloatField(allow_null=True)
    level = serializers.ChoiceField(choices=["ok", "warning", "limit"],
                                    help_text="`warning` from 80 %, `limit` at 100 % (the next create is refused).")
    areas = serializers.ListField(child=serializers.ChoiceField(choices=AREA_NAMES))


class StaffAllowancesSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    areas = serializers.ListField(child=serializers.ChoiceField(choices=AREA_NAMES))
    rows = StaffAllowanceRowSerializer(many=True)


class StaffAllowancesView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        tags=["Admin makerspaces"], summary="Read the limits you manage here and what is left",
        description="Space Managers see every limited resource; other staff only the areas they manage "
                    "(inventory, machines, events, bookings, members, shop, staff). Only limited rows are listed.",
        parameters=[OpenApiParameter("area", str, enum=list(AREA_NAMES), required=False,
                                     description="Narrow to one area (still only those you manage).")],
        request=None, responses={200: StaffAllowancesSerializer, **errors(400, 401, 403, 404)},
    )
    def get(self, request, makerspace_id):
        space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
        if not rbac.effective_actions(request.user, space.pk):
            raise Http404()  # not staff here: do not confirm the space exists
        area = request.query_params.get("area") or None
        if area is not None and area not in AREA_NAMES:
            raise serializers.ValidationError({"area": gettext("Use one of: {areas}.").format(areas=", ".join(AREA_NAMES))})
        return Response(StaffAllowancesSerializer(allowance_rows(request.user, space, area)).data)
