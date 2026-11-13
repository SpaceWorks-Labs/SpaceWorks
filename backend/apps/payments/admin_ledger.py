"""/control/ "Money": the payments ledger and what hangs off it, read-only (0.12.0).

The ledger is core and never tombstoned. Every write -- marking paid with a receipt, refunds,
dispute handling, donations -- runs in the web console through ``apps.payments`` services that
lock the row and write the audit entry; /control/ only lets the superadmin look across spaces.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.payments.donations.models_donations import Donation, DonationCampaign
from apps.payments.models_disputes import PaymentDispute
from apps.payments.models_ledger_entries import LedgerEntry
from apps.payments.models_payment import Payment
from apps.payments.models_refund import Refund
from apps.payments.models_refund_cases import RefundCase
from apps.payments.models_settlement import ManualSettlement
from config.admin_display import record_link, status_badge
from config.admin_records import ControlRecordAdmin


class _PaymentChild(ControlRecordAdmin):
    makerspace_lookup = "payment__makerspace_id"
    list_select_related = ("payment", "payment__makerspace")

    @admin.display(description=_("Payment"), ordering="payment_id")
    def payment_ref(self, obj):
        return record_link(obj, "payment", _("Payment #%(id)s"), "admin:payments_payment_change")

    @admin.display(description=_("Space"), ordering="payment__makerspace__name")
    def space(self, obj):
        return obj.payment.makerspace


@admin.register(Payment)
class PaymentAdmin(ControlRecordAdmin):
    list_display = ("id", "makerspace", "subject_label", "subject_type", "amount", "currency", "status_label",
                    "provider", "due_at", "created_at")
    list_display_links = ("id", "subject_label")
    list_filter = ("status", "provider", "subject_type", "currency")
    search_fields = ("subject_label", "external_order_id", "external_payment_id", "stripe_payment_intent_id",
                     "makerspace__name", "makerspace__slug")
    list_select_related = ("makerspace",)
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    # A hosted checkout link is a bearer link to pay; it is not needed to read the ledger.
    hidden_fields = ("checkout_url", "stripe_checkout_url")
    status_label = status_badge("status")


@admin.register(ManualSettlement)
class ManualSettlementAdmin(_PaymentChild):
    list_display = ("id", "payment_ref", "space", "method", "reference", "amount", "currency", "received_at", "created_at")
    list_filter = ("method", "currency")
    search_fields = ("reference", "payment__makerspace__name")
    ordering = ("-created_at",)
    date_hierarchy = "received_at"


@admin.register(Refund)
class RefundAdmin(_PaymentChild):
    list_display = ("id", "payment_ref", "space", "amount", "currency", "status_label", "provider", "method",
                    "refunded_at", "created_at")
    list_filter = ("status", "provider", "method", "currency")
    search_fields = ("reference", "external_refund_id", "payment__makerspace__name")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    status_label = status_badge("status")


@admin.register(RefundCase)
class RefundCaseAdmin(_PaymentChild):
    list_display = ("id", "payment_ref", "space", "area", "kind", "reason_code", "due_amount", "approved_amount",
                    "status_label", "created_at", "decided_at")
    list_filter = ("status", "area", "kind")
    search_fields = ("reason_code", "payment__makerspace__name")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    hidden_fields = ("member_reason", "decision_note")
    status_label = status_badge("status")


@admin.register(PaymentDispute)
class PaymentDisputeAdmin(ControlRecordAdmin):
    list_display = ("id", "makerspace", "payment_ref", "provider", "amount", "currency", "reason", "status_label",
                    "evidence_due_at", "opened_at")
    list_filter = ("status", "provider", "reason")
    search_fields = ("provider_dispute_id", "makerspace__name")
    list_select_related = ("makerspace",)
    ordering = ("-opened_at",)
    status_label = status_badge("status")

    @admin.display(description=_("Payment"), ordering="payment_id")
    def payment_ref(self, obj):
        return record_link(obj, "payment", _("Payment #%(id)s"), "admin:payments_payment_change")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ControlRecordAdmin):
    list_display = ("id", "makerspace", "entry_date", "kind", "domain", "category", "amount", "currency", "method",
                    "voided_at")
    list_filter = ("kind", "domain", "method", "currency")
    search_fields = ("description", "reference", "makerspace__name")
    list_select_related = ("makerspace",)
    ordering = ("-entry_date", "-id")
    date_hierarchy = "entry_date"
    hidden_fields = ("counterparty",)


@admin.register(Donation)
class DonationAdmin(ControlRecordAdmin):
    list_display = ("id", "makerspace", "campaign", "amount", "currency", "source", "status_label", "created_at",
                    "paid_at")
    list_filter = ("status", "source", "currency")
    search_fields = ("campaign__name", "makerspace__name")
    list_select_related = ("makerspace", "campaign")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    hidden_fields = ("tax_receipt", "tax_detail", "recognize_publicly")
    status_label = status_badge("status")


@admin.register(DonationCampaign)
class DonationCampaignAdmin(ControlRecordAdmin):
    list_display = ("name", "makerspace", "kind", "goal_amount", "currency", "is_active", "is_public", "starts_at",
                    "ends_at")
    list_filter = ("is_active", "is_public", "kind")
    search_fields = ("name", "slug", "makerspace__name")
    list_select_related = ("makerspace",)
    ordering = ("-created_at",)
