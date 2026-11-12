"""Exact authorized subjects project their existing canonical equipment requests."""
from django.apps import apps
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext

from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.hardware_requests.loan_context_access import authorized_request_queryset, safe_id
from .report_types import ReportNotFound, ReportResult
from .reports_ab_common import spaces
from .loan_context_charges import CHARGE_FIELDS, charge_rollup, empty_charges
from .loan_context_report_common import METRIC_FIELDS, QUANTITY_FIELDS, issued_cohort, loan_metrics

FIELDS = ("request_id", "status", "created_at", "issued_at", "return_due_at", "closed_at", "count",
          *QUANTITY_FIELDS, *METRIC_FIELDS, "utilisation", "currency", "estimated_loss_cost", *CHARGE_FIELDS)


def _space(actor, makerspace_id, module):
    if makerspace_id is None or actor is None:
        raise ReportNotFound()
    require_action(actor, rbac.Action.VIEW_INVENTORY, makerspace_id)
    require_action(actor, rbac.Action.VIEW_AUDIT, makerspace_id)
    candidates = spaces(makerspace_id, "request_workflow", module)
    if len(candidates) != 1:
        raise ReportNotFound()
    return candidates[0]


def subject_loans(actor, makerspace_id, subject_kind, subject_id):
    """(space, authorized requests, active links) for one exact event or booking.

    Shared by the equipment and timeline reports so both apply the same tenant,
    module, inventory/audit and per-subject grant before any linked loan is read.
    """
    if subject_kind == "event":
        space = _space(actor, makerspace_id, "events")
        from apps.events import event_authority
        from apps.events.event_permissions import VIEW
        event = get_object_or_404(apps.get_model("events", "Event"), makerspace=space, pk=safe_id(subject_id))
        event_authority.require(actor, event, VIEW)
        contexts = apps.get_model("events", "EventLoanContext").objects.filter(
            makerspace=space, request__makerspace=space, event=event, active=True,
        )
    elif subject_kind == "booking":
        space = _space(actor, makerspace_id, "bookings")
        from apps.bookings import booking_authority
        from apps.bookings.booking_permissions import VIEW
        booking = get_object_or_404(
            apps.get_model("bookings", "Booking").objects.select_related("space__makerspace"),
            space__makerspace=space, pk=safe_id(subject_id),
        )
        booking_authority.require(actor, booking.space, VIEW)
        contexts = apps.get_model("bookings", "BookingLoanContext").objects.filter(
            makerspace=space, request__makerspace=space, booking=booking, active=True,
        )
    else:
        raise ReportNotFound()
    return space, authorized_request_queryset(actor, space), contexts


def _result(contexts, allowed, space, limit, date_range, actor):
    allowed = issued_cohort(allowed, space, date_range)
    contexts = contexts.filter(request_id__in=allowed.values("pk"))
    contexts = contexts.select_related("request").prefetch_related("request__items__product").order_by("request_id")
    if limit is not None:
        contexts = contexts[:limit]
    records = []
    now = timezone.now()
    contexts = list(contexts)
    money = rbac.can(actor, rbac.Action.VIEW_FINANCE, space.pk)
    charges = charge_rollup(space, [context.request_id for context in contexts]) if money else {}
    for context in contexts:
        request = context.request
        records.append({
            "request_id": safe_id(request.pk), "status": request.status,
            "created_at": request.created_at, "issued_at": request.issued_at,
            "return_due_at": request.return_due_at, "closed_at": request.closed_at,
            "count": 1, **loan_metrics(request, now),
            **(charges.get(request.pk) or empty_charges()),
        })
    return ReportResult(FIELDS, records, {
        "basis": gettext("Current active equipment links for this authorized subject, limited to physical loans with a recorded issue time in the selected period; each canonical request appears once. Overdue marks a loan still out past its due time; loan hours run from issue to close, or to now while out. Loss cost is estimated at the current per-unit cost of missing units and is blank when a missing unit is unpriced. Quantities come from the inventory availability projections and utilisation is issued over requested units. Charge and settlement columns are read from the payments ledger and shown to finance readers only. Never-issued requests are excluded."),
        "charges_available": money,
    })


def build_event_equipment(makerspace_id, *, subject_kind, subject_id, actor=None, limit=None, date_range=None):
    if subject_kind != "event":
        raise ReportNotFound()
    space, allowed, contexts = subject_loans(actor, makerspace_id, subject_kind, subject_id)
    return _result(contexts, allowed, space, limit, date_range, actor)


def build_booking_equipment(makerspace_id, *, subject_kind, subject_id, actor=None, limit=None, date_range=None):
    if subject_kind != "booking":
        raise ReportNotFound()
    space, allowed, contexts = subject_loans(actor, makerspace_id, subject_kind, subject_id)
    return _result(contexts, allowed, space, limit, date_range, actor)
