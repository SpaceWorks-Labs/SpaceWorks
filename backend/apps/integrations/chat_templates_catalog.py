"""Staff template contracts for notification events without an email template."""

from .email_templates_registry_helpers import EmailTemplateRegistryEntry, bag


EVENTS = {
    ("hardware_requests", "deposit_raised"): ("request.id", "request.status"),
    ("hardware_requests", "late_fee_raised"): ("request.id", "request.status"),
    ("hardware_requests", "rental_raised"): ("request.id", "request.status"),
    ("hardware_requests", "damage_charged"): ("request.id", "request.status"),
    ("hardware_requests", "lost_charged"): ("request.id", "request.status"),
    ("hardware_requests", "fees_waived"): ("request.id", "request.status"),
    ("hardware_requests", "back_available"): ("product.id", "product.name"),
    ("hardware_requests", "problem_report.filed"): ("problem_report_id",),
    ("api_access", "api_key_request_resolved"): ("request.id", "request.status"),
    ("api_access", "subdomain_request_resolved"): (),
    ("api_access", "space_restore_completed"): (),
    ("api_access", "space_restore_failed"): (),
    ("api_access", "emergency_rekey_started"): (),
    ("api_access", "emergency_rekey_completed"): (),
    ("api_access", "emergency_rekey_failed"): (),
    ("members", "joined"): ("subject.id", "subject.status"),
    ("members", "verified"): ("subject.id", "subject.status"),
    ("members", "vouched"): (),
    # Decision 223: guest-pass notices carry no personal fields beyond the pass window.
    **{("members", event): () for event in ("guest_pass_issued", "guest_pass_expiring", "guest_pass_sponsor_notice")},
    ("members", "join_followup"): (),
    ("stock", "scheduled"): (),
    ("stock", "completed"): (),
    # Machine-service cancellation fans out to staff and rooms (notify_service); the
    # requester leg is an owner self-notice, so only the bounded summary is offered.
    ("printing", "cancelled"): (),
    # Lane L12: loan withdrawals/expiry, automatic To-Buy, and the machine job flow.
    ("hardware_requests", "cancelled"): ("request.id", "request.status"),
    ("hardware_requests", "expired"): ("request.id", "request.status"),
    ("stock", "to_buy_created"): (),
    # Lane L16: issue reports and repair quotes (ids only; never a reporter's details).
    **{(feature, event): ("issue_id",) for feature in ("hardware_requests", "bookings", "maintenance")
       for event in ("issue_reported", "repair_quote_pending")},
    ("maintenance", "repair_dispatched"): (),
    # Release 0.12.0 (decision 223): a reported safety incident (id and area only).
    ("maintenance", "incident_reported"): ("incident_id",),
    # GAP2 M2: item and room maintenance reminders (ids only).
    **{(feature, event): ("schedule_id",) for feature in ("hardware_requests", "bookings")
       for event in ("maintenance_due_soon", "maintenance_overdue")},
    **{("printing", event): () for event in (
        "changes_requested", "resubmitted", "quoted", "quote_approved", "quote_declined", "quote_expired",
        "requeued", "uncollected", "no_show_flagged")},
    # Lane L23: an auto-stopped machine session (owner and staff legs; no room broadcast).
    ("printing", "session_auto_stopped"): (),
    # Release 2 L11: a self-host move's status, a staff leg to Space Managers (rooms=False).
    ("api_access", "selfhost_move_status"): (),
    # Release 2 L18: a sponsor perk coming due fans out to staff and rooms (no giver details).
    ("payments", "perk_due"): (),
    # Release 2 L22: the shop staff's alerts to `manage_shop` holders (ids only; never the buyer).
    **{("payments", event): () for event in ("shop_order_new", "shop_order_unfulfilled", "shop_low_stock",
                                                    "shop_order_ready_for_pickup", "shop_order_picked_up", "shop_order_delivered", "shop_order_pickup_moved")},
    # Release 2 L21a: a member's attendance reply is organiser-facing (catalogued; no producer yet).
    ("events", "attendance_replied"): (),
    # Decision 216: linked event/booking changes and room outages (ids only; never a booker or the
    # event's title, which a booking manager may not be allowed to see).
    ("bookings", "linked_event_changed"): ("booking_id",),
    ("bookings", "room_outage"): ("space_id",),
    ("events", "linked_booking_changed"): ("event_id",),
    # Interconnection 18: link-change webhooks (ids only; destinations alone, no chat copy).
    ("events", "event_booking_linked"): ("event_id", "booking_id"),
    **{("events", name): ("event_id", "request_id") for name in ("event_loan_linked", "event_loan_unlinked")},
    **{("bookings", name): ("booking_id", "request_id") for name in ("booking_loan_linked", "booking_loan_unlinked")},
    # Notifications audit 0.12.0: the organization's hours bank (staff only; ids and the level, no names).
    ("bookings", "hours_bank_low"): ("organization_id", "level"),
    # Decision 221(f): a self-renewal tells staff (ids only); the pickup reminder is personal-only below.
    ("hardware_requests", "renewed"): ("request.id", "request.status"),
}

# These producers explicitly disable staff/room fan-out. Their personal content
# must not become selectable as a staff chat template just because an email
# registry entry exists for the same event.
PERSONAL_ONLY_EVENTS = frozenset({
    ("members", "broadcast"), ("members", "invitation"),
    ("api_access", "email.failed"), ("api_access", "scheduled_report"),
    ("payments", "document_issued"), ("presence", "expired"),
    # Queue-head "next" is an owner self-notice only (service_queue_notices); it never
    # reaches staff or rooms.
    ("printing", "next"),
    # Lane L12: owner reminders and the waitlist offer never reach staff or rooms.
    ("printing", "quote_reminder"), ("printing", "pickup_reminder"),
    ("hardware_requests", "waitlist_offer"),
})
# Events programme notices are addressed to the applicant, team member or certificate
# subject; none has a staff room body.
from .notification_catalog_events_programme import PROGRAMME_EVENTS as _PROGRAMME_EVENTS
PERSONAL_ONLY_EVENTS = PERSONAL_ONLY_EVENTS | frozenset(("events", event) for event in _PROGRAMME_EVENTS)
# Release 2 lanes: notices addressed to one person (an envelope with its own rendered body, or
# a direct email carrying only that person's link). None has a staff leg or a room post.
RELEASE_2_PERSONAL_EVENTS = frozenset({
    # L2 (X37): event and room staff-grant invitations, on the invitee's own channels only.
    ("events", "invitation"), ("bookings", "invitation"),
    # L6: the buyer's order notices, a seat-claim invite, a transfer offer, a pay link and an
    # updated calendar invite (notices_r2_l6, orders_attendees, transfers, orders_pay_link,
    # registration_invites).
    *(("events", event) for event in (
        "order_confirmed", "order_payment_reminder", "order_abandoned", "ticket_type_changed",
        "pass_occurrence_cancelled", "ticket_claim_invite", "ticket_transfer_received", "ticket_pay_link",
        "registration_updated", "pay_window_opened", "pay_window_expired")),
    # L21a: stage advanced, "are you still coming?" and crew notices (notices_r2_l21a).
    *(("events", event) for event in (
        "application_stage_advanced", "attendance_confirmation", "attendance_reminder", "crew_invited",
        "crew_decided")),
    # L21b, #178-#181: judging-source member notices and the winner's payout notice.
    *(("events", event) for event in (
        "finalists_announced", "prize_payout_recorded", "prize_split_proposed", "prize_claim_verified",
        "prize_forfeited", "prize_recovery_opened", "peoples_choice_open", "stage_deadline_reminder",
        "stage_shortlisted", "stage_not_shortlisted", "stage_promoted", "judge_reminder")),
    # L18: the giver's receipt and pledge reminder (fanout staff=False, or a guest's direct email).
    ("payments", "donation_received"), ("payments", "pledge_due"),
    # L22: the shop buyer's order notices (staff=False); the staff alerts are in EVENTS above.
    *(("payments", event) for event in (
        "shop_order_placed", "shop_order_paid", "shop_order_ready", "shop_order_lapsed",
        "shop_order_pickup_moved_to_space", "shop_order_collected",
        "shop_order_cancelled", "shop_order_reminder", "shop_order_receipt")),
    # Decision 216: a borrower told their linked event moved or was cancelled (no staff leg).
    ("hardware_requests", "linked_event_changed"),
    # Interconnection 18: webhook-only link changes have no staff chat or room leg.
    ("events", "event_booking_linked"), ("events", "event_loan_linked"), ("events", "event_loan_unlinked"),
    ("bookings", "booking_loan_linked"), ("bookings", "booking_loan_unlinked"),
    # Decision 221(f): the borrower's pickup-expiring reminder (no staff leg).
    ("hardware_requests", "pickup_expiring"),
    # Notifications audit 0.12.0: the named guardian's consent request (owner only; never names the minor).
    ("members", "guardian_consent_requested"),
    # Decision 221(f): the reporter's repair-closed notice (owner only; rooms=False, staff=False).
    *((feature, "repair_closed") for feature in ("hardware_requests", "bookings", "maintenance")),
})
PERSONAL_ONLY_EVENTS = PERSONAL_ONLY_EVENTS | RELEASE_2_PERSONAL_EVENTS


def chat_only_entry(feature, event):
    names = EVENTS.get((feature, event))
    if names is None:
        return None
    return EmailTemplateRegistryEntry(
        label=event.replace("_", " ").capitalize(),
        description=f"Staff chat notice for {feature}: {event}.",
        fields=[{"name": name, "description": "Event snapshot."}
                for name in names] + [{"name": "makerspace.name", "description": "Makerspace name."}],
        default_subject=event.replace("_", " ").capitalize(),
        default_text="{{ makerspace.name }}: " + event.replace("_", " ") + ".",  # i18n-ignore: composed from the event key, not authored copy
        default_html="",
        sample_context={"makerspace": bag(name="Demo workshop"), "problem_report_id": 12,
                        "request": bag(id=12, status="pending"),
                        "product": bag(id=12, name="Torque wrench"),
                        "subject": bag(id=12, status="active")},
    )
