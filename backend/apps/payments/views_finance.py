"""Finance ledger screens: income vs spending, and the per-event money view (X55).

Scoped per area through `finance_scope` (#100); 404 while `finance.ledger` is off. The
same numbers export through the report registry (`income-spending`, `finance-*`,
`event-finance`), where the PII export rules apply.
"""

from django.utils.translation import gettext
import csv
from datetime import date, timedelta
from io import StringIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.local_time import local_day_bounds, local_now
from apps.payments.l5_gates import finance_space
from apps.payments.reports_finance_ledger import EVENT_FIELDS, FIELDS, build_income_spending, event_finance

ERRORS = {400: OpenApiResponse(ErrorSerializer), 401: OpenApiResponse(ErrorSerializer),
          403: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer)}
RANGE = [OpenApiParameter("from", OpenApiTypes.DATE, description="First local day (default: 12 months ago)."),
         OpenApiParameter("to", OpenApiTypes.DATE, description="Last local day, inclusive (default: today).")]


class SummaryRowSerializer(serializers.Serializer):
    month = serializers.CharField()
    domain = serializers.CharField()
    machine_type = serializers.CharField(allow_blank=True)
    currency = serializers.CharField()
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    other_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    refunds = serializers.DecimalField(max_digits=14, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=14, decimal_places=2)
    payouts = serializers.DecimalField(max_digits=14, decimal_places=2)
    money_in = serializers.DecimalField(max_digits=14, decimal_places=2)
    money_out = serializers.DecimalField(max_digits=14, decimal_places=2)
    net = serializers.DecimalField(max_digits=14, decimal_places=2)


class SummarySerializer(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()
    rows = SummaryRowSerializer(many=True)


class EventFinanceRowSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    event = serializers.CharField(allow_blank=True)
    currency = serializers.CharField()
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    refunds = serializers.DecimalField(max_digits=14, decimal_places=2)
    other_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=14, decimal_places=2)
    payouts = serializers.DecimalField(max_digits=14, decimal_places=2)
    budget = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    budget_left = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    net = serializers.DecimalField(max_digits=14, decimal_places=2)


class EventBudgetSerializer(serializers.Serializer):
    currency = serializers.RegexField(r"^[a-z]{3}$")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


def _range(request, space):
    def parse(name):
        value = request.query_params.get(name)
        try:
            return date.fromisoformat(value) if value else None
        except ValueError:
            raise ValidationError({name: gettext("Use YYYY-MM-DD.")})
    today = local_now(space).date()
    end = parse("to") or today
    start = parse("from") or (end.replace(day=1) - timedelta(days=330)).replace(day=1)
    if start > end or (end - start).days > 1100:
        raise ValidationError({"from": gettext("Choose a range of at most three years.")})
    return start, end, (local_day_bounds(space, start)[0], local_day_bounds(space, end + timedelta(days=1))[0])


class FinanceSummaryView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="Income versus spending by month, area and machine type",
                   description="Every money movement in the caller's finance areas: member charges collected, "
                               "other receipts, refunds, expenses and event payouts. Never mixes currencies.",
                   parameters=RANGE, responses={200: SummarySerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space, _view = finance_space(request, makerspace_id)
        start, end, window = _range(request, space)
        result = build_income_spending(space.pk, date_range=window, actor=request.user)
        return Response({"start": start, "end": end, "rows": result.records})


def _event(space, event_id):
    from apps.events.models import Event

    return get_object_or_404(Event.objects.filter(makerspace=space), pk=event_id)


class EventFinanceView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="One event's money: income less refunds and spending, against budget",
                   description="Event Manager or finance staff. `format=csv` downloads the same rows.",
                   parameters=[OpenApiParameter("format", OpenApiTypes.STR, enum=["json", "csv"])],
                   responses={200: EventFinanceRowSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id, event_id):
        space, view = finance_space(request, makerspace_id)
        if not view.sees("events"):
            raise PermissionDenied(gettext("Events money is for the Event Manager and finance staff."))
        event = _event(space, event_id)
        rows = event_finance(space, None, request.user, event.pk)
        if request.query_params.get("format") == "csv":
            buffer = StringIO()
            writer = csv.DictWriter(buffer, fieldnames=EVENT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="event-{event.pk}-money.csv"'
            return response
        return Response(EventFinanceRowSerializer(rows, many=True).data)


class EventBudgetView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="Set an event's finance budget for one currency",
                   description="Event Manager or finance staff. Appends a revision; the newest is the budget. "
                               "Audited `ledger.event_budget_set`.",
                   request=EventBudgetSerializer, responses={200: EventBudgetSerializer, **ERRORS})
    def put(self, request, makerspace_id, event_id):
        from apps.payments.models_event_budget import EventFinanceBudget
        from apps.tenant_migration.gate_runtime import assert_write_allowed

        space, view = finance_space(request, makerspace_id)
        if not view.may_record("events"):
            raise PermissionDenied(gettext("Event budgets are set by the Event Manager or finance staff."))
        event = _event(space, event_id)
        payload = EventBudgetSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        assert_write_allowed(space.pk)
        row = EventFinanceBudget.objects.create(makerspace=space, event=event, event_id_snapshot=event.pk,
                                                set_by=request.user, **payload.validated_data)
        audit.record(request.user, "ledger.event_budget_set", makerspace=space, target=event,
                     meta={"currency": row.currency, "budget_id": row.pk})
        return Response(EventBudgetSerializer(row).data)


__all__ = ["EventBudgetView", "EventFinanceView", "FIELDS", "FinanceSummaryView"]
