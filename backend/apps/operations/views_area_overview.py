"""Grouped area views for each area manager and the combined Space Manager view (decision 241).

`GET admin/makerspace/{id}/area-overview/{section}` with section = finance | tobuy | consumables |
repairs | warranties. Each view reads only its own list's scoped source (rbac, finance_scope,
machines role scope, procurement and repairs authority), so an area manager gets their own
area's rows and the Space Manager every area, grouped by area (machines: type, then
machine; inventory: item category) with per-group totals. Read-only, so no audit entry.
Handout-only desk roles are refused (224(d)); payout money is session-only (224(c), 226(g)).
"""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from apps.payments.money_fields import MoneyField
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.servability import servable_queryset

VIEWS = ("finance", "tobuy", "consumables", "repairs", "warranties")
AREAS = ("inventory", "machines", "bookings", "events", "shop", "membership", "donations", "general")
STATUSES = {
    "tobuy": ("open", "all", "requested", "approved", "ordered", "received", "cancelled"),
    "repairs": ("open", "all", "reported", "triaged", "assigned", "in_progress", "fixed", "closed", "rejected"),
    "consumables": ("low", "ok"),
    "warranties": ("active", "expiring_soon", "expired", "unknown"),
}
ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (400, 401, 403, 404)}


class AreaMoneySerializer(serializers.Serializer):
    currency = serializers.CharField(allow_blank=True, help_text="Blank for To-Buy costs, which carry no currency.")
    amount = MoneyField(max_digits=17, decimal_places=3)


class AreaFinanceTotalsSerializer(serializers.Serializer):
    currency = serializers.CharField()
    income = MoneyField(max_digits=17, decimal_places=3)
    other_income = MoneyField(max_digits=17, decimal_places=3)
    refunds = MoneyField(max_digits=17, decimal_places=3)
    expenses = MoneyField(max_digits=17, decimal_places=3)
    owed = MoneyField(max_digits=17, decimal_places=3, help_text="Charges still pending today.")
    money_in = MoneyField(max_digits=17, decimal_places=3)
    payouts = MoneyField(max_digits=17, decimal_places=3, required=False,
                                       help_text="Interactive sessions only (decision 224(c)).")
    money_out = MoneyField(max_digits=17, decimal_places=3, required=False)
    net = MoneyField(max_digits=17, decimal_places=3, required=False)


class AreaItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField(allow_blank=True)
    status = serializers.CharField(allow_blank=True)
    source = serializers.CharField(required=False)
    priority = serializers.CharField(required=False)
    quantity = serializers.CharField(required=False)
    unit = serializers.CharField(required=False)
    threshold = serializers.CharField(required=False, allow_null=True)
    amount = MoneyField(max_digits=17, decimal_places=3, required=False, allow_null=True)
    currency = serializers.CharField(required=False, allow_blank=True)
    expires_on = serializers.DateField(required=False, allow_null=True)


class AreaGroupSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["area", "domain", "machine_type", "machine", "category", "room", "event"])
    key = serializers.CharField(help_text="Unique among siblings; `<kind>:none` holds rows tied to no one thing.")
    label = serializers.CharField(allow_blank=True, help_text="A record name; blank for area keys and none groups.")
    count = serializers.IntegerField()
    attention = serializers.IntegerField(help_text="Rows needing action: owed, requested, low, open or expiring.")
    money = AreaMoneySerializer(many=True)
    finance = AreaFinanceTotalsSerializer(many=True)
    items = AreaItemSerializer(many=True)


AreaGroupSerializer._declared_fields["children"] = AreaGroupSerializer(many=True)


class AreaOverviewSerializer(serializers.Serializer):
    view = serializers.ChoiceField(choices=VIEWS)
    areas = serializers.ListField(child=serializers.CharField(), help_text="Areas present for this caller.")
    totals = AreaGroupSerializer()
    groups = AreaGroupSerializer(many=True)
    truncated = serializers.BooleanField(help_text="More rows exist than the item cap lists; totals still count all.")


def _areas_param(request):
    raw = request.query_params.get("area", "")
    chosen = {value for value in raw.split(",") if value}
    if chosen - set(AREAS):
        raise ValidationError({"area": gettext("Choose areas from: %(areas)s.") % {"areas": ", ".join(AREAS)}})
    return chosen or None


def _status_param(request, view):
    value = request.query_params.get("status") or None
    if value is not None and value not in STATUSES.get(view, ()):
        raise ValidationError({"status": gettext("This status does not apply to this list.")})
    return value


def _space(request, makerspace_id):
    return get_object_or_404(rbac.scope_by_makerspace(request.user, servable_queryset(), makerspace_field="pk"),
                             pk=makerspace_id)


class AreaOverviewView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Finance"], summary="One area list grouped by area, machine type, machine or item category",
        description="Decision 241. `finance`: income, refunds, expenses, payouts and charges owed now, for the "
                    "caller's finance areas only (a Machine Manager only their machine types). `tobuy`, "
                    "`consumables`, `repairs`, `warranties`: the caller's own scoped rows. Machines group by "
                    "type then machine; inventory by item category. Payout figures need an interactive session.",
        parameters=[
            OpenApiParameter("section", OpenApiTypes.STR, OpenApiParameter.PATH, enum=list(VIEWS)),
            OpenApiParameter("area", OpenApiTypes.STR, description="Comma-separated area filter."),
            OpenApiParameter("status", OpenApiTypes.STR, description="List filter; values depend on the view."),
            OpenApiParameter("from", OpenApiTypes.DATE, description="Finance only: first local day."),
            OpenApiParameter("to", OpenApiTypes.DATE, description="Finance only: last local day, inclusive."),
        ],
        responses={200: AreaOverviewSerializer, **ERRORS})
    def get(self, request, makerspace_id, section):
        view = section
        if view not in VIEWS:
            raise NotFound()
        if rbac.is_handout_only(request.user, makerspace_id):
            raise NotFound()  # 224(d): the counter roles get a counter-only API
        areas = _areas_param(request)
        status = _status_param(request, view)
        tree, present = self._tree(request, makerspace_id, view, areas, status)
        payouts = view != "finance" or _full_session(request)
        groups = tree.groups(payouts=payouts)
        if present is None:
            present = [group["key"].split(":", 1)[1] for group in groups]
        return Response({"view": view, "areas": present, "totals": tree.totals(payouts=payouts),
                         "groups": groups, "truncated": tree.truncated})

    @staticmethod
    def _tree(request, makerspace_id, view, areas, status):
        if view == "finance":
            from apps.operations.area_overview_finance import finance_tree, visible_areas
            from apps.payments.l5_gates import finance_space
            from apps.payments.views_finance import _range

            space, finance = finance_space(request, makerspace_id)
            _start, _end, window = _range(request, space)
            return finance_tree(request.user, space, finance, date_range=window, areas=areas), visible_areas(finance)
        space = _space(request, makerspace_id)
        if view == "tobuy":
            from apps.operations.area_overview_upkeep import tobuy_tree
            return tobuy_tree(request.user, space, areas=areas, status=status or "open"), None
        if view == "consumables":
            from apps.operations.area_overview_upkeep import consumables_tree
            return consumables_tree(request.user, space, areas=areas, status=status), None
        if view == "repairs":
            from apps.operations.area_overview_care import repairs_tree
            return repairs_tree(request.user, space, areas=areas, status=status or "open"), None
        from apps.operations.area_overview_care import warranties_tree
        return warranties_tree(request.user, space, areas=areas, status=status), None


def _full_session(request):
    from apps.payments.payout_session import full_session
    return full_session(request)
