"""Presentation entries: Payment, payment-rail and member-card audit actions.

Generated from the audit AST discovery, then reviewed. Every literal action has one
entry; ``permitted`` lists only reviewed non-personal LEAF paths (no names, free
text, secrets, object keys or before/after payloads)."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("member_card.created", gettext_noop("Member card created"), ("card_id",)),
    P("member_card.issued", gettext_noop("Member card issued"), ("card_id",)),
    P("member_card.name_updated", gettext_noop("Member card name updated"), ("card_id",)),
    P("member_card.photo_removed", gettext_noop("Member card photo removed"), ("card_id",)),
    P("member_card.photo_updated", gettext_noop("Member card photo updated"), ("card_id",)),
    P("member_card.printed", gettext_noop("Member card printed"), ("card_id", "count")),
    P("member_card.reissued", gettext_noop("Member card reissued"), ("card_id", "reason")),
    P("member_card.revoked", gettext_noop("Member card revoked"), ("card_id",)),
    P("member_card.scanned", gettext_noop("Member card scanned"), ("outcome", "qr_id")),
    P("member_card.template_updated", gettext_noop("Member card template updated"), ("version",)),
    P("payment.canceled", gettext_noop("Payment canceled")),
    P("payment.checkout_created", gettext_noop("Payment checkout created"),
      ("payment_id", "provider", "subject_id", "subject_type")),
    P("payment.checkout_expired", gettext_noop("Payment checkout expired"), ("stripe_event_id",)),
    P("payment.created", gettext_noop("Payment created"),
      ("amount", "currency", "payment_id", "subject_id", "subject_type", "via_makerspace_id", "discount_id")),
    P("payment.double_paid_refund_required", gettext_noop("Payment double paid refund required"),
      ("event_id", "prior_status", "provider", "provider_payment_id", "stripe_event_id")),
    P("payment.mobile_intent_created", gettext_noop("Payment mobile intent created"), ("stripe_provider",)),
    P("payment.paid_after_terminal", gettext_noop("Payment paid after terminal"),
      ("event_id", "prior_status", "provider", "provider_payment_id", "resolved_status", "stripe_event_id")),
    P("payment.paid_offline", gettext_noop("Payment paid offline")),
    P("payment.paid_online", gettext_noop("Payment paid online"),
      ("event_id", "late_capture", "polled", "provider", "stripe_event_id",
       "capture_mismatch", "captured_minor", "captured_currency")),
    P("payment.refund_failed", gettext_noop("Payment refund failed")),
    P("payment.refund_policy_updated", gettext_noop("Payment refund policy updated"),
      ("area", "fields", "plan_id", "removed")),
    P("payment.refund_requested", gettext_noop("Payment refund requested"),
      ("amount", "payment_id", "refund_id", "outcome_unknown")),
    P("payment.refunded", gettext_noop("Payment refunded")),
    P("payment.settlement_amended", gettext_noop("Payment settlement amended"),
      ("amends_id", "method", "previous_method", "settlement_id")),
    P("payment.waived", gettext_noop("Payment waived")),
    P("payments.connect_account_mapped", gettext_noop("Payments connect account mapped")),
    P("payments.connect_authorization_revoked", gettext_noop("Payments connect authorization revoked")),
    P("payments.connect_callback_consumed", gettext_noop("Payments connect callback consumed")),
    P("payments.connect_deauthorization_ignored", gettext_noop("Payments connect deauthorization ignored")),
    P("payments.connect_deauthorized", gettext_noop("Payments connect deauthorized")),
    P("payments.connect_onboarded", gettext_noop("Payments connect onboarded")),
    P("payments.connect_onboarding_started", gettext_noop("Payments connect onboarding started")),
    P("payments.connect_previous_authorization_revoked", gettext_noop("Payments connect previous authorization revoked"),
      ),
    P("payments.connect_status_update_ignored", gettext_noop("Payments connect status update ignored")),
    P("payments.connect_status_updated", gettext_noop("Payments connect status updated")),
    P("payments.settings_updated", gettext_noop("Payments settings updated")),
)
