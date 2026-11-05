"""The source module or capability of every notification the platform can send (#183B).

A notification whose source is off for a space is never emitted or delivered: no inbox
row, no room post, no email, no push. Three vocabularies are covered:

* the catalogue (`notification_catalog.FEATURE_EVENTS`): each family's default source is
  `recipients_selection.FEATURE_MODULES`, and `EVENT_SOURCES` narrows single events to the
  capability that actually produces them (a shop order needs `shop`, a donation receipt
  `finance.donations`). An override only ever NARROWS: the family's own source must be on
  as well, so this map can stop a notification but never widen who receives one;
* staff alerts written by `notifications.emit.emit_notification`, keyed by the dotted
  prefix of their `event` (`EMIT_SOURCES`);
* `None` means platform-level: always on, because no single space switch owns it.

A dotted key is a capability, a bare key a module, and `a|b` is live while either is on
(the To-Buy list serves two parents), exactly as `operations.report_sources` reads them.
`tests/modules/test_notification_source_map.py` fails on an unmapped or unknown key.
"""
import logging

from .notification_enums import NotificationFeature as F

logger = logging.getLogger(__name__)

_HW, _PR, _EV, _BK, _MT, _MB, _PAY, _API, _CERT = (
    F.HARDWARE_REQUESTS, F.PRINTING, F.EVENTS, F.BOOKINGS, F.MAINTENANCE, F.MEMBERS, F.PAYMENTS,
    F.API_ACCESS, F.CERTIFICATIONS,
)


def _many(feature, events, source):
    return {(feature, event): source for event in events}


EVENT_SOURCES = {
    # Lending: optional loan features each have their own switch.
    (_HW, "waitlist_offer"): "loans.waitlist",
    (_HW, "back_available"): "inventory.notify_when_back",
    (_HW, "fees_waived"): "loans.fee_waivers",
    (_HW, "issue_reported"): "inventory.issue_reporting",
    (_HW, "repair_quote_pending"): "inventory.repairs",
    **_many(_HW, ("maintenance_due_soon", "maintenance_overdue"), "inventory.maintenance"),
    # Machine jobs: quotes and sessions are capabilities under their machine modules.
    **_many(_PR, ("quoted", "quote_reminder", "quote_approved", "quote_declined", "quote_expired"),
            "machines.job_quotes"),
    (_PR, "session_auto_stopped"): "machines.sessions",
    # Rooms.
    (_BK, "issue_reported"): "bookings.issue_reporting",
    (_BK, "repair_quote_pending"): "bookings.room_repairs",
    (_BK, "invitation"): "bookings.staff_grants",
    **_many(_BK, ("maintenance_due_soon", "maintenance_overdue"), "bookings.room_maintenance"),
    # Machine maintenance family: problem reports and repairs are not maintenance.
    (_MT, "issue_reported"): "machines.issue_reporting",
    **_many(_MT, ("repair_quote_pending", "repair_dispatched"), "machines.repairs"),
    # Events: each optional programme feature.
    **_many(_EV, ("order_confirmed", "order_payment_reminder", "order_abandoned"), "events.orders"),
    (_EV, "ticket_type_changed"): "events.ticket_types",
    (_EV, "pass_occurrence_cancelled"): "events.series_passes",
    (_EV, "ticket_transfer_received"): "events.transfers",
    (_EV, "approval_digest"): "events.approval_digest",
    (_EV, "mentor_help_alert"): "events.mentor_chat_alerts",
    **_many(_EV, ("application_submitted", "application_offered", "application_waitlisted",
                  "application_rejected", "application_confirmed", "application_declined",
                  "application_expired", "application_withdrawn"), "events.applications"),
    (_EV, "application_stage_advanced"): "events.application_stages",
    **_many(_EV, ("attendance_confirmation", "attendance_reminder", "attendance_replied"),
            "events.attendance_confirmation"),
    **_many(_EV, ("crew_invited", "crew_decided"), "events.crew"),
    (_EV, "finalists_announced"): "events.finalists",
    (_EV, "prize_payout_recorded"): "events.prize_payouts",
    # Submission stages (#178-#180) live inside hackathon programmes; People's choice has its own switch (#181).
    **_many(_EV, ("stage_deadline_reminder", "stage_shortlisted", "stage_not_shortlisted", "stage_promoted",
                  "judge_reminder"), "events.hackathons"),
    (_EV, "peoples_choice_open"): "events.peoples_choice",
    # Members.
    (_MB, "broadcast"): "membership.broadcasts",
    (_MB, "vouched"): "membership.vouching",
    **_many(_MB, ("erasure_approved", "erasure_rejected"), "membership.erasure"),
    (_MB, "programme_card_decided"): "membership.id_programmes",
    (_MB, "event_card_issued"): "events.id_cards",
    # Money: the ledger is core; the optional money features are not.
    **_many(_PAY, ("shop_order_placed", "shop_order_paid", "shop_order_ready", "shop_order_lapsed",
                   "shop_order_cancelled", "shop_order_unfulfilled", "shop_order_reminder",
                   "shop_order_receipt", "shop_order_new", "shop_low_stock"), "shop"),
    (_PAY, "donation_received"): "finance.donations",
    (_PAY, "pledge_due"): "finance.recurring_donations",
    (_PAY, "perk_due"): "finance.sponsors",
    (_PAY, "dispute_opened"): "billing.disputes",
    (_PAY, "capture_flagged"): "billing.capture_flags",
    (_PAY, "document_issued"): "billing.documents",
    **_many(_PAY, ("paid_claim_received", "paid_claim_confirmed", "paid_claim_rejected"),
            "billing.offline_claims"),
    # Platform family: only these two have a space switch.
    (_API, "scheduled_report"): "reports",
    (_API, "email.failed"): "email",
    **_many(_CERT, ("granted", "revoked", "expiring", "expired"), "machines.certifications"),
}

# Staff alerts (`emit_notification`), by the dotted prefix of their event key. Reminder
# sweeps pass their own builder's event and are gated by their ReminderSource module and
# capability before they reach the emitter, so they are listed in EMIT_EXEMPT instead.
EMIT_SOURCES = {
    "request.": "request_workflow",
    "loan.": "request_workflow",
    "problem_report.": "request_workflow",
    "machine_service.": "machine_service",
    "stocktake.": "stocktake",
    "email.": "email",
}
# `destination_auto_disabled` is delivery health for the notifications module itself.
EMIT_EXEMPT = frozenset({"destination_auto_disabled"})


def family_source(feature):
    from .recipients_selection import FEATURE_MODULES
    return FEATURE_MODULES.get(feature)


def event_source(feature, event):
    """The narrower switch one catalogue event needs on top of its family's, or None."""
    return EVENT_SOURCES.get((feature, event))


def emit_source(event):
    for prefix, source in EMIT_SOURCES.items():
        if (event or "").startswith(prefix):
            return source
    return None


def source_live(makerspace, source):
    """True while `source` (module, capability or `a|b`) is on; `None` is always on."""
    if source is None or makerspace is None:
        return True
    from apps.operations.report_sources import source_enabled
    return source_enabled(makerspace, source)


def event_live(makerspace, feature, event):
    """False when a catalogue event's own capability is off for this space.

    The family's module stays gated where it always was (`recipients.feature_available`,
    which also knows the per-source-kind exceptions); this adds the event's narrower switch
    at every delivery chokepoint. Fail-closed on a lookup error, as matrix resolution is.
    """
    source = event_source(feature, event)
    if source is None or makerspace is None:
        return True
    try:
        return source_live(makerspace, source)
    except Exception:
        logger.warning("notification_source_check_failed",
                       extra={"makerspace_id": getattr(makerspace, "pk", None), "feature": feature, "event": event})
        return False


def emit_live(makerspace, event):
    """False when the source of a staff alert (`emit_notification`) is off for this space."""
    try:
        return source_live(makerspace, emit_source(event))
    except Exception:
        logger.warning("notification_emit_source_check_failed",
                       extra={"makerspace_id": getattr(makerspace, "pk", None), "event": event})
        return False
