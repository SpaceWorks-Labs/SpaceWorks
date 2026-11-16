"""Typed dashboard counters, including optional programme families."""

from rest_framework import serializers
from .serializers_report_chart import ReportChartSpecSerializer
from .serializers_attention import AttentionSerializer


class DashboardWidgetSerializer(serializers.Serializer):
    key = serializers.CharField()
    title = serializers.CharField()
    required_action = serializers.CharField()
    required_modules = serializers.ListField(child=serializers.CharField())
    kind = serializers.ChoiceField(choices=["count", "trend", "top_n", "heatmap", "queue"])
    report_keys = serializers.ListField(child=serializers.CharField())
    default_period = serializers.IntegerField(help_text="Inclusive local calendar days.")
    data = serializers.DictField(child=serializers.JSONField(), help_text=(
        "Deferred widget: meta.start/end are tenant-local calendar labels. Fetch "
        "report_keys[0] independently through the tenant analytics endpoint."))
    chart_spec = ReportChartSpecSerializer(allow_null=True)


class DashboardQueueSerializer(serializers.Serializer):
    ready_to_issue = serializers.IntegerField(required=False)
    due_returns = serializers.IntegerField(required=False)
    pickups = serializers.IntegerField(required=False)
    due_today = serializers.IntegerField(required=False)
    overdue = serializers.IntegerField(required=False)
    to_record = serializers.IntegerField(required=False)


class NextUpEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    href = serializers.CharField()


class DashboardSerializer(serializers.Serializer):
    next_up_events = NextUpEventSerializer(many=True, required=False)
    upcoming_events = serializers.IntegerField(required=False, default=0)
    pending_event_registrations = serializers.IntegerField(required=False, default=0)
    pending_bookings = serializers.IntegerField(required=False, default=0)
    upcoming_bookings = serializers.IntegerField(required=False, default=0)
    open_booking_issues = serializers.IntegerField(required=False, default=0)
    # EB12/BK3: today (the space's local day) and room outages over the next 7 days.
    today_events = serializers.IntegerField(required=False, default=0)
    today_check_ins = serializers.IntegerField(required=False, default=0)
    today_bookings = serializers.IntegerField(required=False, default=0)
    room_outages_week = serializers.IntegerField(required=False, default=0)
    failed_areas = serializers.ListField(
        child=serializers.CharField(), required=False, default=list,
        help_text="Areas whose counters could not be loaded (U13); their counts read 0.")
    scope_mode = serializers.ChoiceField(choices=["machine", "full", "handover"])
    attention = AttentionSerializer(required=False, help_text="Per-area counters (decision 242).")
    widgets = DashboardWidgetSerializer(many=True, required=False)
    queue_tiles = DashboardQueueSerializer(required=False)
    overdue_loans = serializers.IntegerField(required=False, default=0)
    pending_requests = serializers.IntegerField(required=False, default=0)
    due_today_loans = serializers.IntegerField(required=False, default=0)
    due_soon_loans = serializers.IntegerField(required=False, default=0)
    true_low_stock = serializers.IntegerField(required=False, default=0)
    in_repair = serializers.IntegerField(required=False, default=0)
    awaiting_issue = serializers.IntegerField(required=False, default=0)
    payments_to_record = serializers.IntegerField(required=False, default=0)
    open_problem_reports = serializers.IntegerField(required=False, default=0)
    low_stock = serializers.IntegerField(required=False, default=0)
    pending_prints = serializers.IntegerField(required=False, default=0)
    active_prints = serializers.IntegerField(required=False, default=0)
    prints_awaiting_collection = serializers.IntegerField(required=False, default=0)
    failed_emails = serializers.IntegerField(required=False, default=0)
    stocktakes_awaiting_approval = serializers.IntegerField(required=False, default=0)
    warranty_expiring = serializers.IntegerField(required=False, default=0)
    maintenance_overdue = serializers.IntegerField(required=False, default=0)
    pending_payments = serializers.IntegerField(required=False, default=0)
    # Declared so the schema and the generated TypeScript carry it: the endpoint emits
    # this map and an undeclared field is invisible to typed frontend consumers. Amounts
    # are strings keyed by currency code -- never one combined number, since adding INR
    # to USD would be meaningless money.
    outstanding_by_currency = serializers.DictField(
        child=serializers.CharField(), required=False, default=dict
    )
