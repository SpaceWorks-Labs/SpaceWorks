"""Payloads for a loan's repair handoff and its read-only repair context.

The repair's work order, parts and To-Buy rows reuse their own serializers; the line's
return photo travels as an id only (its bytes stay behind the evidence endpoint).
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.maintenance.views_work_orders import WorkOrderSerializer
from apps.procurement.serializers import ToBuyItemSerializer

from .models_issues import IssueReport
from .serializers_issues import RepairPartSerializer


class LoanRepairHandoffSerializer(serializers.Serializer):
    accountability_id = serializers.IntegerField(min_value=1, help_text="The damaged return line to repair.")
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class LoanRepairIssueSerializer(serializers.ModelSerializer):
    work_order = WorkOrderSerializer(read_only=True, allow_null=True)
    parts = RepairPartSerializer(many=True, read_only=True)
    to_buy_items = serializers.SerializerMethodField()
    payout_amount = serializers.SerializerMethodField()
    payout_currency = serializers.SerializerMethodField()

    class Meta:
        model = IssueReport
        fields = ["id", "state", "title", "priority", "quote_state", "quote_amount", "quote_currency",
                  "payout_entry_id", "payout_amount", "payout_currency", "work_order", "parts", "to_buy_items",
                  "created_at", "fixed_at", "closed_at"]
        read_only_fields = fields

    @extend_schema_field(ToBuyItemSerializer(many=True))
    def get_to_buy_items(self, row):
        """Only the To-Buy rows this viewer may see (`procurement.access.scope_items`)."""
        visible = self.context.get("to_buy", {})
        rows = [visible[part.to_buy_item_id] for part in row.parts.all() if part.to_buy_item_id in visible]
        return ToBuyItemSerializer(rows, many=True, context=self.context).data

    def _payout(self, row):
        events = [event for event in row.events.all() if event.kind == "payout"]
        return events[-1] if events else None

    def get_payout_amount(self, row) -> str | None:
        event = self._payout(row)
        return None if event is None or event.amount is None else str(event.amount)

    def get_payout_currency(self, row) -> str:
        event = self._payout(row)
        return event.currency if event is not None else ""


class LoanRepairLineSerializer(serializers.Serializer):
    accountability_id = serializers.IntegerField()
    request_item_id = serializers.IntegerField(allow_null=True)
    product_name = serializers.CharField()
    quantity = serializers.IntegerField()
    asset_id = serializers.IntegerField(allow_null=True)
    asset_tag = serializers.CharField(allow_blank=True)
    remark = serializers.CharField(allow_blank=True)
    evidence_id = serializers.IntegerField(allow_null=True, help_text="The return photo, by id only.")
    handed_off = serializers.BooleanField(help_text="A repair is already open for this line.")
    issue = LoanRepairIssueSerializer(
        allow_null=True, help_text="Repair detail (parts, quote, cost); null for a reviewer who is not an item manager.")


class LoanRepairsSerializer(serializers.Serializer):
    request_id = serializers.IntegerField()
    lines = LoanRepairLineSerializer(many=True)


class LoanRepairHandoffResultSerializer(serializers.Serializer):
    created = serializers.BooleanField(help_text="False when this line was already handed off (idempotent replay).")
    issue_id = serializers.IntegerField()
    line = LoanRepairLineSerializer()
