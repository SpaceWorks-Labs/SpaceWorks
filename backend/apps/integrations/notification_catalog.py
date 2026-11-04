"""Feature/channel catalog + default state for the notification matrix (Part K).

The DEFAULT_CHANNEL_STATE table is the authoritative default when no explicit
NotificationPreference row exists — nothing is backfilled. Resolution is fail-closed:
a preference-query failure logs and returns False for that channel, never raising.
"""
import logging

from apps.integrations.models import (
    NotificationChannel,
    NotificationFeature,
    NotificationPreference,
)

logger = logging.getLogger(__name__)

F = NotificationFeature
C = NotificationChannel

# Lifecycle events routed through the fan-out per feature (spec section 6). Draft/CRUD/
# document/status-only actions stay audit-only and are intentionally absent.
FEATURE_EVENTS = {
    F.HARDWARE_REQUESTS: (
        "submitted", "accepted", "rejected", "issued", "partially_returned",
        "returned", "closed_with_issue", "return_reminder",
        "deposit_raised", "late_fee_raised",
        # Lane L15: rental, damage and lost charges, and staff fee waivers.
        "rental_raised", "damage_charged", "lost_charged", "fees_waived",
        "overdue_escalated", "back_available", "problem_report.filed",
        # Lane L12: withdrawn and expired requests, and a waitlist offer.
        "cancelled", "expired", "waitlist_offer",
        # Lane L16: an item problem reported, a repair quote awaiting approval.
        "issue_reported", "repair_quote_pending",
    ),
    F.PRINTING: (
        "submitted", "accepted", "started", "rejected", "completed", "failed",
        "collected", "reprinted", "next", "cancelled",
        # Lane L12, the uniform job flow (#141): review, quotes, re-queue, pickup.
        "changes_requested", "resubmitted", "quoted", "quote_reminder", "quote_approved", "quote_declined",
        "quote_expired", "requeued", "pickup_reminder", "uncollected", "no_show_flagged",
        # Lane L23: a machine session stopped itself (max length, check-out, closing).
        "session_auto_stopped",
    ),
    F.EVENTS: (
        "published", "cancelled", "completed", "registration_created",
        "registration_pending_approval", "registration_waitlisted",
        "registration_approved", "registration_rejected",
        "registration_cancelled", "registration_restored", "registration_promoted", "registration_attended",
        "series_published", "series_cancelled", "series_completed",
        "series_generation_failed",
        "reminder",
    ),
    F.BOOKINGS: (
        "created", "confirmed", "rejected", "cancelled", "restored", "completed", "no_show",
        "reminder",
        # Lane L16: a room problem reported, a repair quote awaiting approval.
        "issue_reported", "repair_quote_pending",
    ),
    F.MAINTENANCE: (
        "schedule_created", "schedule_updated", "schedule_deactivated", "logged",
        "schedule_completed",
        "due_soon", "overdue",
        # Lane L16: a machine problem reported, a repair quote awaiting approval, and the
        # technician send (only its WhatsApp template binding reads this key).
        "issue_reported", "repair_quote_pending", "repair_dispatched",
    ),
    # request_pending is the existing application-received event; keep its stable key.
    F.MEMBERS: ("request_pending", "member_joined", "approved", "declined",
                "renewal_due", "lapsed", "renewal_failed", "awaiting_payment", "payment_due",
                "renewed", "grace_started", "cancelled", "broadcast", "joined", "verified", "invitation", "vouched"),
    F.API_ACCESS: ("api_key_request_resolved", "subdomain_request_resolved", "email.failed", "scheduled_report",
                   "space_restore_completed", "space_restore_failed"),
    F.DEVICES: ("offline", "recovered"),
    F.PAYMENTS: ("charge_raised", "payment_due_soon", "payment_due_today", "payment_overdue",
                 "payment_received", "refund_issued", "payment_failed", "document_issued",
                 "refund_due_opened", "refund_request_received", "refund_request_approved",
                 "refund_request_declined", "paid_claim_received", "paid_claim_confirmed",
                 "paid_claim_rejected", "settlement_awaiting_confirmation", "capture_flagged",
                 "dispute_opened"),
    F.STOCK: ("low_stock", "procurement_received", "scheduled", "completed", "to_buy_created"),
    F.CERTIFICATIONS: ("granted", "revoked", "expiring", "expired"),
}
from .notification_catalog_events_programme import PROGRAMME_EVENTS
FEATURE_EVENTS[F.EVENTS] += PROGRAMME_EVENTS
# Release 2 L2 (X37): staff-grant invitations offered on the invitee's own chat channels.
FEATURE_EVENTS[F.EVENTS] += ("invitation",)
FEATURE_EVENTS[F.BOOKINGS] += ("invitation",)
# Release 2 L4 (X29): the member's per-space erasure decision.
FEATURE_EVENTS[F.MEMBERS] += ("erasure_approved", "erasure_rejected")
# Release 2 L8 (#120, C-26): an emergency re-key, told to the space's Space Managers.
FEATURE_EVENTS[F.API_ACCESS] += ("emergency_rekey_started", "emergency_rekey_completed", "emergency_rekey_failed")
# Release 2 L11: a self-host move's status, told to the space's Space Managers.
FEATURE_EVENTS[F.API_ACCESS] += ("selfhost_move_status",)
# Release 2 L3: cards issued (member, programme and event cards), a design awaiting approval,
# a "photo needs update" request, a finished card job, and ID-programme decisions.
FEATURE_EVENTS[F.MEMBERS] += ("card_issued", "card_design_pending", "card_photo_requested", "card_job_finished",
                              "programme_card_decided", "event_card_issued")
# Release 2 L6: ticket orders, seat claims, transfers, type changes, pass occurrences, venue fees.
FEATURE_EVENTS[F.EVENTS] += ("order_confirmed", "order_payment_reminder", "order_abandoned", "ticket_type_changed",
                             "pass_occurrence_cancelled", "ticket_claim_invite", "ticket_transfer_received",
                             "registration_updated", "ticket_pay_link")

# Exact default on/off per (feature, channel). Preserves today's behavior: hardware/printing
# email + hardware Telegram on; bookings email (Part J seam) + bookings Telegram on; Slack/
# Mattermost/Discord always opt-in; events/maintenance have no prior external behavior → off.
# Discord is listed explicitly rather than relying on default_state's False fallback, so the
# table stays a complete picture of every channel a reader can toggle.
DEFAULT_CHANNEL_STATE = {
    F.HARDWARE_REQUESTS: {C.EMAIL: True, C.TELEGRAM: True, C.SLACK: False, C.MATTERMOST: False, C.DISCORD: False, C.WEBHOOK: False, C.NATIVE_PUSH: False},
    F.PRINTING: {C.EMAIL: True, C.TELEGRAM: False, C.SLACK: False, C.MATTERMOST: False, C.DISCORD: False, C.WEBHOOK: False, C.NATIVE_PUSH: False},
    F.EVENTS: {C.EMAIL: False, C.TELEGRAM: False, C.SLACK: False, C.MATTERMOST: False, C.DISCORD: False, C.WEBHOOK: False, C.NATIVE_PUSH: False},
    F.BOOKINGS: {C.EMAIL: True, C.TELEGRAM: True, C.SLACK: False, C.MATTERMOST: False, C.DISCORD: False, C.WEBHOOK: False, C.NATIVE_PUSH: False},
    F.MAINTENANCE: {C.EMAIL: False, C.TELEGRAM: False, C.SLACK: False, C.MATTERMOST: False, C.DISCORD: False, C.WEBHOOK: False, C.NATIVE_PUSH: False},
    F.MEMBERS: {C.EMAIL: False, C.TELEGRAM: False, C.SLACK: False, C.MATTERMOST: False, C.DISCORD: False, C.WEBHOOK: False, C.NATIVE_PUSH: False},
    # Preserve the old resolution email + Telegram default, now mutable and metered.
    F.API_ACCESS: {C.EMAIL: True, C.TELEGRAM: True, C.SLACK: False, C.MATTERMOST: False, C.DISCORD: False, C.WEBHOOK: False, C.NATIVE_PUSH: False},
    F.DEVICES: {channel: False for channel in C.values},
    F.PAYMENTS: {channel: False for channel in C.values},
    F.STOCK: {channel: False for channel in C.values},
    F.CERTIFICATIONS: {channel: False for channel in C.values},
}

# Hardware/printing already emit directly; their matrix inbox is explicitly opt-in.
for _feature, _channels in DEFAULT_CHANNEL_STATE.items():
    _channels[C.SMS] = False
    _channels[C.WHATSAPP] = False
    _channels[C.IN_APP] = _feature not in {F.HARDWARE_REQUESTS, F.PRINTING}
    _channels[C.WHATSAPP] = False


from .notification_catalog_p2_presence import register as register_presence
register_presence(FEATURE_EVENTS, DEFAULT_CHANNEL_STATE)


def default_state(feature, channel):
    """The catalog default for a cell (False for any unknown feature/channel)."""
    return DEFAULT_CHANNEL_STATE.get(feature, {}).get(channel, False)


def is_notification_enabled(makerspace, feature, channel):
    """Resolve the (feature, channel) cell: explicit override wins, else the catalog default.

    Fail-closed: any DB error resolving the override logs and returns False for that channel
    so a lookup failure can never break a workflow or silently over-notify.
    """
    try:
        override = (
            NotificationPreference.objects.filter(
                makerspace=makerspace, feature=feature, channel=channel
            )
            .values_list("enabled", flat=True)
            .first()
        )
    except Exception:
        logger.warning(
            "notification_preference_lookup_failed",
            extra={
                "makerspace_id": getattr(makerspace, "pk", None),
                "feature": feature,
                "channel": channel,
            },
        )
        return False
    if override is not None:
        return override
    return default_state(feature, channel)


def receipt_email_default(makerspace):
    """Only the payer's receipt defaults on; an explicit matrix OFF still wins."""
    try:
        override = NotificationPreference.objects.filter(
            makerspace=makerspace, feature=F.PAYMENTS, channel=C.EMAIL,
        ).values_list("enabled", flat=True).first()
        return True if override is None else bool(override)
    except Exception:
        logger.warning("receipt_preference_lookup_failed", extra={"makerspace_id": makerspace.pk})
        return False
