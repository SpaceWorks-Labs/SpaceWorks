"""The cost fields every maintenance-run write shares (#102: parts and costs go to the ledger)."""

from rest_framework import serializers

from apps.payments.models_ledger_entries import LedgerEntry


class MaintenanceCostFields(serializers.Serializer):
    cost_method = serializers.ChoiceField(
        choices=LedgerEntry.Method.choices, required=False, allow_blank=True, default="other",
        help_text="How the cost was paid (blank: other). With a cost above zero the run records a maintenance expense in the "
                  "finance ledger (cash goes to the cash account, everything else to the bank account).")
    cost_currency = serializers.CharField(
        min_length=3, max_length=3, required=False, allow_blank=True, default="",
        help_text="Three-letter currency code; blank uses the space's default payment currency.")
