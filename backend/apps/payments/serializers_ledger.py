"""Finance-ledger request and response shapes (lane L5, #94/#100)."""

from decimal import Decimal

from rest_framework import serializers

from apps.payments.models_ledger_entries import LedgerEntry, OpeningBalance
from apps.payments.serializers_l5 import page_of


class LedgerEntrySerializer(serializers.ModelSerializer):
    has_receipt = serializers.SerializerMethodField()
    receipt_kind = serializers.SerializerMethodField(help_text="`pdf`, `image`, or blank without a receipt.")
    event_id = serializers.IntegerField(read_only=True, allow_null=True)
    machine_type_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = LedgerEntry
        fields = ("id", "kind", "domain", "machine_type_id", "machine_type_label", "event_id", "category", "method",
                  "account", "amount", "currency", "entry_date", "description", "counterparty", "reference",
                  "source_kind", "source_id", "has_receipt", "receipt_kind", "created_at", "voided_at", "void_reason")
        read_only_fields = fields

    def get_has_receipt(self, entry) -> bool:
        return entry.receipt_id is not None

    def get_receipt_kind(self, entry) -> str:
        if entry.receipt_id is None:
            return ""
        return "pdf" if entry.receipt.content_type == "application/pdf" else "image"


class LedgerEntryCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=LedgerEntry.Kind.choices)
    domain = serializers.ChoiceField(choices=LedgerEntry.Domain.choices)
    machine_type_id = serializers.IntegerField(required=False, allow_null=True)
    event_id = serializers.IntegerField(required=False, allow_null=True)
    category = serializers.ChoiceField(choices=sorted({*LedgerEntry.RECEIPT_CATEGORIES, *LedgerEntry.EXPENSE_CATEGORIES}))
    method = serializers.ChoiceField(choices=LedgerEntry.Method.choices)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.RegexField(r"^[a-zA-Z]{3}$")
    entry_date = serializers.DateField()
    description = serializers.CharField(max_length=300)
    counterparty = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    reference = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    receipt_id = serializers.IntegerField(required=False, allow_null=True,
                                          help_text="An uploaded receipt from the receipt-upload route.")

    def validate(self, attrs):
        allowed = (LedgerEntry.RECEIPT_CATEGORIES if attrs["kind"] == LedgerEntry.Kind.RECEIPT
                   else LedgerEntry.EXPENSE_CATEGORIES)
        if attrs["category"] not in allowed:
            raise serializers.ValidationError({"category": "Choose a category for this kind of entry."})
        if attrs.get("machine_type_id") and attrs["domain"] != LedgerEntry.Domain.MACHINES:
            raise serializers.ValidationError({"machine_type_id": "Only machines entries name a machine type."})
        return attrs


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


class ReceiptUploadRequestSerializer(serializers.Serializer):
    # Images and, for receipts only, PDF (#155). The presign binds the chosen type.
    content_type = serializers.ChoiceField(choices=["image/jpeg", "image/png", "image/webp", "application/pdf"])
    size_bytes = serializers.IntegerField(min_value=1, required=False)


class ReceiptUploadSerializer(serializers.Serializer):
    evidence_id = serializers.IntegerField()
    upload_url = serializers.CharField()
    fields = serializers.DictField(child=serializers.CharField())
    object_key = serializers.CharField()
    method = serializers.CharField(required=False)
    headers = serializers.DictField(child=serializers.CharField(), required=False)


class ReceiptUrlSerializer(serializers.Serializer):
    url = serializers.CharField()


class OpeningBalanceSerializer(serializers.ModelSerializer):
    currency = serializers.RegexField(r"^[a-z]{3}$")
    cash_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal("0"))
    bank_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal("0"))

    class Meta:
        model = OpeningBalance
        fields = ("fy_start", "currency", "cash_amount", "bank_amount", "set_at")
        read_only_fields = ("set_at",)


class FinanceViewSerializer(serializers.Serializer):
    everything = serializers.BooleanField()
    domains = serializers.ListField(child=serializers.CharField())
    machine_type_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=True)
    record_domains = serializers.ListField(child=serializers.CharField())
    record_everything = serializers.BooleanField()


LedgerEntryPage = page_of(LedgerEntrySerializer, "LedgerEntryPage")
