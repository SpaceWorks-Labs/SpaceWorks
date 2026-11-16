from django.utils import timezone
from .target_projection_types import TargetField
from .tenant_dump_types import AuthorityDisposition as D, authority

EVENT_FIELD_PROJECTION = {
    **{(label, "organization_admission_blocked"): TargetField(
        True, reason="Portable organization references are excluded; staff must explicitly review target-local audience.")
       for label in ("events.Event", "events.EventSeries")},
    **{(label, field): TargetField(use_model_default=True, reason="Source keyed code/contact digests are never target credentials.") for label, field in (("events.EventInvite", "code_digest"), ("events.EventInvite", "email_digest"), ("events.EventPromoCode", "code_digest"))},
    ("events.EventRegistration", "pay_by"): TargetField(None, reason="A running pay window is not carried to the target."),
    **{(label, "revoked_at"): TargetField(resolver=timezone.now, reason="Source codes cannot grant admission or discounts on target.")
       for label in ("events.EventInvite", "events.EventPromoCode")},
}
EVENT_AUTHORITY_ENTRIES = tuple(
    ((label, field), authority(D.RESET, "Target reissues event access/discount credentials."))
    for label, field in (
        ("events.EventInvite", "code_digest"), ("events.EventInvite", "email_digest"),
        ("events.EventInvite", "revoked_at"), ("events.EventPromoCode", "code_digest"),
        ("events.EventPromoCode", "revoked_at"),
    )
) + tuple(
    ((label, "organization_admission_blocked"), authority(D.RESET, "Target staff must deliberately review imported organization admission."))
    for label in ("events.Event", "events.EventSeries")
) + tuple(
    (edge, authority(D.PRESERVE, reason))
    for edge, reason in (
        (("events.Event", "show_registration_count"), "Portable publication choice; public serializers suppress counts when false."),
        (("events.EventRegistration", "cancelled_at"), "Historical cancellation provenance; the target server clock still enforces the five-minute window."),
        (("events.EventRegistration", "status_before_cancel"), "Historical cancellation state; exact undo still requires live target authority and ordinary admission."),
        (("events.EventRegistration", "waitlist_position_at"), "Portable FIFO position preserves the original queue or an audited tail restore."),
        (("makerspaces.Makerspace", "event_default_registration_audience"), "Portable event admission default; target module and feature gates still apply."),
        (("events.Event", "registration_audience"), "Portable event admission policy; target module and feature gates still apply."),
        (("events.EventSeries", "registration_audience"), "Portable series admission template; target module and feature gates still apply."),
        (("events.EventRegistration", "registration_audience"), "Historical admission provenance grants reads only to the active owner of this exact registration."),
        (("events.EventTicketType", "audience"), "Portable price eligibility; member pricing requires live target membership proof."),
        (("events.EventTicketType", "is_active"), "Portable sales state; target events and ticketing gates still apply."),
    )
)
EVENT_AUDIT_EDGES = {
    ("event.invite_redeemed", "invite_id"): "events.EventInvite",
    ("event.promo_redeemed", "promo_id"): "events.EventPromoCode",
}
