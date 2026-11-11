"""The linked finance view of one event (decision 216 item 8): each section from its own owner.

Read-only; raises nothing and records nothing. Sections, each independently gated and
omitted when hidden:

* `registration_charges` -- the event's own charges (Events owns them; the core ledger
  records them). Event Manager or finance staff (`finance_scope` sees `events`). Hidden
  when event charge tracking is off AND nothing was ever recorded, so historic debt stays
  visible after the switch is turned off.
* `venue_fee` -- the event-owned hosting fee (`events.venue_fees`). Same authority.
* `booking_room_charge` -- the linked booking's room charge, labelled Booking-owned and read
  only. Needs the `bookings` module and booking finance authority (`finance_scope` sees
  `bookings`). Counted once: it is never folded into the event's registration or budget
  totals (its ledger domain is `bookings`).
* `reimbursements` -- the `event_reimbursements` module's claims; finance staff or an event
  grant holding `review_reimbursements`; full sessions only.
* `payouts` -- the core payout ledger; finance staff (`view_finance`) only, full sessions only.

"Full session" means an interactive account session: payee money is never read by an API
client, a personal access token or an OAuth app connection (decision 219d).
* `budget` -- budget against actuals (`reports_finance_ledger.event_finance`); needs the
  `finance.ledger` capability and events finance authority.

Every amount is grouped by currency; nothing is summed across currencies.
"""

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.payments.payout_session import full_session as _full_session
from apps.payments.event_linked_finance_totals import (
    booking_chain_ids, booking_payments, charge_totals, event_charge_payments, minor_amount, venue_fee_payments,
)




def _registration(space, event):
    from apps.payments.availability import charge_tracking_enabled

    payments = event_charge_payments(space, event)
    tracking = charge_tracking_enabled(space, "events")
    if not tracking and not payments.exists():
        return None
    return {"owner": "events", "source": "payments.Payment", "tracking_enabled": tracking,
            "currencies": charge_totals(payments)}


def _venue_fee(space, event, linked):
    from apps.events.models import EventVenueFee

    fee = EventVenueFee.objects.filter(makerspace=space, event=event).first()
    if fee is None and (linked or not feature_enabled(space, "events.venue_fees")):
        return None
    totals = charge_totals(venue_fee_payments(space, fee)) if fee is not None else []
    return {"owner": "events", "source": "events.EventVenueFee", "status": fee.status if fee else "none",
            "currencies": totals}


def _booking_room_charge(space, decision):
    ids = booking_chain_ids(space, decision.booking_id) if decision.booking_id else []
    return {"owner": "bookings", "label": "Booking-owned", "read_only": True, "source": "bookings.Booking",
            "state": "linked" if ids else "booking_unavailable", "booking_ids": ids,
            "currencies": charge_totals(booking_payments(space, ids))}


def _reimbursements(event):
    from apps.event_reimbursements.finance_summary import event_totals

    rows = []
    for currency, values in sorted(event_totals(event).items()):
        rows.append({"currency": currency, "submitted_count": values["submitted_count"],
                     "submitted": minor_amount(values["submitted_minor"], currency),
                     "approved_count": values["approved_count"],
                     "approved": minor_amount(values["approved_minor"], currency),
                     "paid": minor_amount(values["paid_minor"], currency)})
    return {"owner": "event_reimbursements", "source": "event_reimbursements.ReimbursementClaim",
            "currencies": rows}


def _payouts(space, event):
    from django.db.models import Count, Sum

    from apps.payments.event_payouts.obligation_models import EventPayoutObligation
    from apps.payments.event_payouts.payout_models import EventPayoutEntry

    obligations = EventPayoutObligation.objects.filter(makerspace=space, event_id_snapshot=event.pk)
    groups = {}
    for row in obligations.order_by().values("currency").annotate(n=Count("pk"), total=Sum("approved_minor")):
        currency = row["currency"].lower()
        groups[currency] = {"obligations": row["n"], "approved_minor": row["total"] or 0, "paid_minor": 0,
                            "by_method": {}}
    entries = EventPayoutEntry.objects.filter(obligation__in=obligations, is_void=False, amended_by__isnull=True)
    for row in entries.order_by().values("currency", "method").annotate(total=Sum("amount_minor")):
        bucket = groups.setdefault(row["currency"].lower(), {"obligations": 0, "approved_minor": 0,
                                                             "paid_minor": 0, "by_method": {}})
        bucket["paid_minor"] += row["total"] or 0
        bucket["by_method"][row["method"]] = bucket["by_method"].get(row["method"], 0) + (row["total"] or 0)
    rows = []
    for currency, values in sorted(groups.items()):
        rows.append({"currency": currency, "obligations": values["obligations"],
                     "approved": minor_amount(values["approved_minor"], currency),
                     "paid": minor_amount(values["paid_minor"], currency),
                     "remaining": minor_amount(max(values["approved_minor"] - values["paid_minor"], 0), currency),
                     "paid_by_method": {key: minor_amount(value, currency)
                                        for key, value in sorted(values["by_method"].items())}})
    return {"owner": "payments.event_payouts", "source": "payments.EventPayoutObligation",
            "settlement": "offline", "currencies": rows}


def _budget(space, event, actor):
    from apps.payments.reports_finance_ledger import event_finance

    keep = ("currency", "income", "refunds", "other_income", "expenses", "payouts", "budget", "budget_left", "net")
    rows = [{key: row[key] for key in keep} for row in event_finance(space, None, actor, event.pk)]
    return {"owner": "payments.EventFinanceBudget", "source": "payments.finance_rows", "currencies": rows}


def may_view_event(actor, space, event):
    from apps.events import event_authority, event_permissions

    return (rbac.can(actor, rbac.Action.MANAGE_EVENTS, space.pk) or rbac.can(actor, rbac.Action.VIEW_FINANCE, space.pk)
            or event_authority.can(actor, event, event_permissions.VIEW))


def linked_finance(request, space, event):
    """`{section: payload}` for every section the actor may see; empty when none."""
    from apps.events import event_authority, event_permissions
    from apps.events.models_booking_decision import EventBookingDecision
    from apps.payments.finance_scope import finance_view

    actor = request.user
    view = finance_view(actor, space.pk)
    finance = rbac.can(actor, rbac.Action.VIEW_FINANCE, space.pk)
    decision = EventBookingDecision.objects.filter(makerspace=space, event=event).first()
    sections = {}
    if view.sees("events"):
        registration = _registration(space, event)
        if registration is not None:
            sections["registration_charges"] = registration
        venue = _venue_fee(space, event, decision is not None)
        if venue is not None:
            sections["venue_fee"] = venue
        # The budget rows carry event payout totals (and net/budget_left derived from them):
        # payee money is session-only (#219d), so tokens and OAuth clients get no budget section.
        if feature_enabled(space, "finance.ledger") and _full_session(request):
            sections["budget"] = _budget(space, event, actor)
    if decision is not None and module_enabled(space, "bookings") and view.sees("bookings"):
        sections["booking_room_charge"] = _booking_room_charge(space, decision)
    if (_full_session(request) and module_enabled(space, "event_reimbursements")
            and (finance or event_authority.can(actor, event, event_permissions.REVIEW_REIMBURSEMENTS))):
        sections["reimbursements"] = _reimbursements(event)
    if _full_session(request) and finance:
        sections["payouts"] = _payouts(space, event)
    return sections
