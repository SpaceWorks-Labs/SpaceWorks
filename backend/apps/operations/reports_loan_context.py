"""Count canonical requests without disclosing private contextual relationships."""
from decimal import Decimal

from django.apps import apps
from django.db.models import Case, CharField, Exists, OuterRef, Value, When
from django.utils import timezone
from django.utils.translation import gettext

from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.makerspaces.platform import module_enabled
from .report_types import ReportNotFound, ReportResult
from .reports_ab_common import spaces
from .loan_context_charges import CHARGE_FIELDS, charge_rollup, empty_charges
from .loan_context_report_common import METRIC_FIELDS, QUANTITY_FIELDS, issued_cohort, loan_metrics, utilisation

SUMMED = (*QUANTITY_FIELDS, *METRIC_FIELDS)
MONEY_FIELDS = tuple(field for field in CHARGE_FIELDS if field != "charge_currency")
FIELDS = ("context", "status", "currency", "charge_currency", "count", *QUANTITY_FIELDS, *METRIC_FIELDS,
          "utilisation", "estimated_loss_cost", "unpriced_loss_loans", *MONEY_FIELDS)


def _context_visible(actor, space):
    # Keep the whole cohort uniform when either dimension is unavailable. An
    # inventory-only reader must not infer a hidden link from a missing row.
    return all(
        module_enabled(space, module) and rbac.can(actor, action, space.pk)
        for module, action in (
            ("events", rbac.Action.MANAGE_EVENTS),
            ("bookings", rbac.Action.MANAGE_BOOKINGS),
        )
    )


def _with_context(rows, space):
    # Optional models are resolved only after deployment and tenant gates pass.
    # EXISTS preserves one row per loan even when the request has many items.
    events = apps.get_model("events", "EventLoanContext").objects.filter(
        request_id=OuterRef("pk"), makerspace_id=space.pk,
        event__makerspace_id=space.pk, active=True,
    )
    bookings = apps.get_model("bookings", "BookingLoanContext").objects.filter(
        request_id=OuterRef("pk"), makerspace_id=space.pk,
        booking__space__makerspace_id=space.pk, active=True,
    )
    return rows.annotate(_event_context=Exists(events), _booking_context=Exists(bookings)).annotate(
        context=Case(
            When(_event_context=True, _booking_context=True, then=Value(gettext("Event and booking"))),
            When(_event_context=True, then=Value(gettext("Event"))),
            When(_booking_context=True, then=Value(gettext("Booking"))),
            default=Value(gettext("Ordinary loan")), output_field=CharField(),
        )
    )


def build_loan_purpose_summary(makerspace_id, *, actor=None, limit=None, date_range=None):
    if makerspace_id is None or actor is None:
        raise ReportNotFound()
    require_action(actor, rbac.Action.VIEW_INVENTORY, makerspace_id)
    from apps.hardware_requests.loan_context_access import authorized_request_queryset

    records = []
    disclosed = False
    money_shown = False
    for space in spaces(makerspace_id, "request_workflow"):
        rows = authorized_request_queryset(actor, space)
        rows = issued_cohort(rows, space, date_range)
        disclosed = _context_visible(actor, space)
        rows = _with_context(rows, space) if disclosed else rows.annotate(
            context=Value(gettext("Context not shown"), output_field=CharField()),
        )
        # Each request is measured once, then lands in exactly one mutually exclusive
        # purpose bucket; summing any column across rows is the canonical total.
        now = timezone.now()
        groups = {}
        loans = list(rows.order_by("pk").prefetch_related("items__product"))
        # Money is the finance reader's: everyone else sees the same rows with the money columns empty.
        money = rbac.can(actor, rbac.Action.VIEW_FINANCE, space.pk)
        money_shown = money_shown or money
        charges = charge_rollup(space, [loan.pk for loan in loans]) if money else {}
        for request in loans:
            metrics = loan_metrics(request, now)
            charge = charges.get(request.pk) or empty_charges()
            key = (request.context, request.status, metrics["currency"], charge["charge_currency"])
            group = groups.setdefault(key, dict(
                zip(("context", "status", "currency", "charge_currency"), key), count=0,
                estimated_loss_cost=Decimal("0"), unpriced_loss_loans=0,
                **dict.fromkeys(SUMMED, 0), **{field: empty_charges()[field] for field in MONEY_FIELDS}))
            group["count"] += 1
            for field in SUMMED:
                group[field] += metrics[field]
            for field in MONEY_FIELDS:
                group[field] += charge[field]
            if metrics["estimated_loss_cost"] is None:
                group["unpriced_loss_loans"] += 1
            else:
                group["estimated_loss_cost"] += metrics["estimated_loss_cost"]
        ordered = [groups[key] for key in sorted(groups)]
        for group in ordered:
            group["loan_hours"] = round(group["loan_hours"], 2)
            group["utilisation"] = utilisation(group["issued_units"], group["requested_units"])
        records.extend(ordered if limit is None else ordered[:limit])
    return ReportResult(FIELDS, records, {
        "basis": gettext("Current purpose and status of authorized physical loans with a recorded issue time in the selected period. Each canonical request counts once, in exactly one purpose: a loan linked to both an event and a booking appears only under Event and booking, so column sums are overall totals. Overdue counts loans still out past their due time; loan hours run from issue to close, or to now while out. Loss cost is estimated at the current per-unit cost of missing units, per currency; loans with an unpriced missing unit are counted separately. Requested, reserved and outstanding units come from the inventory availability projections: reserved is stock held for an accepted request awaiting handover (zero once issued) and outstanding is issued minus returned, damaged and missing. Utilisation is issued units over requested units. Charges are the loan's deposit, late fee, rental, damage and lost-item rows read from the payments ledger, with pending, paid (online or offline) and waived amounts per currency and the count of effective offline receipts; they are shown to finance readers only. Never-issued requests are excluded."),
        "context_dimensions_available": disclosed,
        "charges_available": money_shown,
    })
