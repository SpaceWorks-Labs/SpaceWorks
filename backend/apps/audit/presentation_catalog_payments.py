"""Presentation entries: Payment, payment-rail and member-card audit actions.

Generated from the audit AST discovery, then reviewed. Every literal action has one
entry; ``permitted`` lists only reviewed non-personal LEAF paths (no names, free
text, secrets, object keys or before/after payloads)."""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("member_card.created", gettext_lazy("Member card created"), ("card_id",)),
    P("member_card.issued", gettext_lazy("Member card issued"), ("card_id",)),
    P("member_card.name_updated", gettext_lazy("Member card name updated"), ("card_id",)),
    P("member_card.photo_removed", gettext_lazy("Member card photo removed"), ("card_id",)),
    P("member_card.photo_updated", gettext_lazy("Member card photo updated"), ("card_id",)),
    P("member_card.printed", gettext_lazy("Member card printed"), ("card_id", "count")),
    P("member_card.reissued", gettext_lazy("Member card reissued"), ("card_id",)),
    P("member_card.revoked", gettext_lazy("Member card revoked"), ("card_id",)),
    P("member_card.scanned", gettext_lazy("Member card scanned"), ("outcome", "qr_id")),
    P("member_card.template_updated", gettext_lazy("Member card template updated"), ("version",)),
    P("payment.canceled", gettext_lazy("Payment canceled")),
    P("payment.checkout_created", gettext_lazy("Payment checkout created"),
      ("payment_id", "provider", "subject_id", "subject_type")),
    P("payment.checkout_expired", gettext_lazy("Payment checkout expired"), ("stripe_event_id",)),
    P("payment.created", gettext_lazy("Payment created"),
      ("amount", "currency", "payment_id", "subject_id", "subject_type", "via_makerspace_id", "discount_id")),
    P("payment.double_paid_refund_required", gettext_lazy("Payment double paid refund required"),
      ("event_id", "prior_status", "provider", "stripe_event_id")),
    P("payment.mobile_intent_created", gettext_lazy("Payment mobile intent created"), ("stripe_provider",)),
    P("payment.paid_after_terminal", gettext_lazy("Payment paid after terminal"),
      ("event_id", "prior_status", "provider", "resolved_status", "stripe_event_id")),
    P("payment.paid_offline", gettext_lazy("Payment paid offline")),
    P("payment.paid_online", gettext_lazy("Payment paid online"),
      ("event_id", "late_capture", "polled", "provider", "stripe_event_id")),
    P("payment.refund_failed", gettext_lazy("Payment refund failed")),
    P("payment.refund_policy_updated", gettext_lazy("Payment refund policy updated"),
      ("area", "fields", "plan_id", "removed")),
    P("payment.refund_requested", gettext_lazy("Payment refund requested"),
      ("amount", "payment_id", "refund_id")),
    P("payment.refunded", gettext_lazy("Payment refunded")),
    P("payment.settlement_amended", gettext_lazy("Payment settlement amended"),
      ("amends_id", "method", "previous_method", "settlement_id")),
    P("payment.waived", gettext_lazy("Payment waived")),
    P("payments.connect_account_mapped", gettext_lazy("Payments connect account mapped")),
    P("payments.connect_authorization_revoked", gettext_lazy("Payments connect authorization revoked")),
    P("payments.connect_callback_consumed", gettext_lazy("Payments connect callback consumed")),
    P("payments.connect_deauthorization_ignored", gettext_lazy("Payments connect deauthorization ignored")),
    P("payments.connect_deauthorized", gettext_lazy("Payments connect deauthorized")),
    P("payments.connect_onboarded", gettext_lazy("Payments connect onboarded")),
    P("payments.connect_onboarding_started", gettext_lazy("Payments connect onboarding started")),
    P("payments.connect_previous_authorization_revoked", gettext_lazy("Payments connect previous authorization revoked"),
      ),
    P("payments.connect_status_update_ignored", gettext_lazy("Payments connect status update ignored")),
    P("payments.connect_status_updated", gettext_lazy("Payments connect status updated")),
    P("payments.settings_updated", gettext_lazy("Payments settings updated")),
)
