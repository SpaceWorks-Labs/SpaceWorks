"""Lifecycle timeline of one event's or booking's linked loans, read from source history.

Every milestone comes from a record the request workflow already wrote: the
request's own lifecycle timestamps, immutable ReturnEvent rows, and the
append-only `request.rejected` audit entry (rejection stamps no column). Nothing
here is stored or derived from chat; read-only.
"""
from django.utils.translation import gettext

from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.return_models import ReturnEvent
from .report_types import ReportNotFound, ReportResult
from .reports_ab_common import calendar_range
from .reports_loan_context_details import subject_loans

FIELDS = ("occurred_at", "request_id", "milestone", "status", "count")
TERMINAL = (
    HardwareRequest.Status.RETURNED, HardwareRequest.Status.CLOSED_WITH_ISSUE,
    HardwareRequest.Status.CANCELLED, HardwareRequest.Status.EXPIRED,
)


def _milestones(requests, space):
    by_id = {request.pk: request for request in requests}
    for request in requests:
        yield request.created_at, request, "requested"
        if request.accepted_at:
            yield request.accepted_at, request, "accepted"
        if request.issued_at:
            yield request.issued_at, request, "issued"
        if request.status in TERMINAL and request.closed_at:
            yield request.closed_at, request, request.status
    for request_id, at in ReturnEvent.objects.filter(
        makerspace=space, request_id__in=by_id,
    ).values_list("request_id", "created_at"):
        yield at, by_id[request_id], "return_recorded"
    for target_id, at in AuditLog.objects.filter(
        makerspace=space, action="request.rejected",
        target_type=HardwareRequest._meta.label_lower, target_id__in=[str(pk) for pk in by_id],
    ).values_list("target_id", "created_at"):
        yield at, by_id[int(target_id)], "rejected"


def _timeline(actor, makerspace_id, subject_kind, subject_id, limit, date_range):
    space, allowed, contexts = subject_loans(actor, makerspace_id, subject_kind, subject_id)
    requests = list(allowed.filter(pk__in=contexts.values("request_id")).exclude(
        status=HardwareRequest.Status.DRAFT).order_by("pk"))
    start, end = calendar_range(date_range, space) or (None, None)
    rows = sorted(
        (at, request.pk, milestone, request.status)
        for at, request, milestone in _milestones(requests, space)
        if (start is None or at >= start) and (end is None or at < end)
    )
    if limit is not None:
        rows = rows[:limit]
    return ReportResult(FIELDS, [
        dict(zip(FIELDS, (*row, 1))) for row in rows
    ], {
        "basis": gettext("Lifecycle milestones of loans currently linked to this authorized subject, from the request's recorded times, each return record and the rejection audit entry, in time order. Requests are included once submitted, whether or not they were issued; the period filters milestones, not loans. A loan linked to several activities appears in each activity's timeline but is still one request."),
    })


def build_event_loan_timeline(makerspace_id, *, subject_kind, subject_id, actor=None, limit=None, date_range=None):
    if subject_kind != "event":
        raise ReportNotFound()
    return _timeline(actor, makerspace_id, subject_kind, subject_id, limit, date_range)


def build_booking_loan_timeline(makerspace_id, *, subject_kind, subject_id, actor=None, limit=None, date_range=None):
    if subject_kind != "booking":
        raise ReportNotFound()
    return _timeline(actor, makerspace_id, subject_kind, subject_id, limit, date_range)
