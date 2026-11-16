"""Personal usage facts: every query binds both the member and selected tenant."""

from collections import Counter
from decimal import Decimal

from django.db.models import Count, DateTimeField, Sum
from django.db.models.functions import Coalesce

from apps.hardware_requests.models import HardwareRequest, PublicToolLoan, ReturnEvent
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.operations.report_definitions_ab import chart
from apps.operations.reports_common import period_expression


def series(rows, x, values, *, time=True, currency=None, top=None):
    spec = chart(x, values, time=time, partition="currency" if currency else None,
                 currency=currency, top=top)
    # Personal charts have no tenant dimension: each query already binds one tenant.
    spec["series"] = [currency] if currency else []
    return {"rows": rows, "chart_spec": spec}


def _months(queryset, field, space):
    return queryset.annotate(period=period_expression(field, "month", makerspace=space))


def _counts(queryset, field, space):
    return Counter({row["period"].date().isoformat(): row["count"] for row in
                    _months(queryset.filter(**{f"{field}__isnull": False}), field, space)
                    .values("period").annotate(count=Count("pk")).order_by("period")})


def loans(space, member):
    direct = PublicToolLoan.objects.filter(makerspace=space, requester=member)
    reviewed = HardwareRequest.objects.filter(makerspace=space, requester=member).exclude(
        pk__in=PublicToolLoan.objects.filter(makerspace=space).values("request_id"),
    )
    issued = reviewed.filter(issued_at__isnull=False)
    returned = issued.filter(status=HardwareRequest.Status.RETURNED)
    direct_returns = direct.filter(returned_at__isnull=False)
    issued_months = _counts(issued, "issued_at", space) + _counts(direct, "checked_out_at", space)
    returns = ReturnEvent.objects.filter(makerspace=space, request__makerspace=space, request__requester=member)
    # Partial returns belong to their event month. Only legacy direct returns with
    # no event use returned_at, and linked direct/workflow records never double count.
    returned_months = _counts(returns, "created_at", space) + _counts(
        direct_returns.exclude(request_id__in=returns.values("request_id")), "returned_at", space,
    )
    rows = [{"period": month, "issued_count": issued_months[month], "return_events": returned_months[month]}
            for month in sorted(issued_months.keys() | returned_months.keys())]
    return {
        "count": issued.count() + direct.count(),
        "returned_count": returned.count() + direct_returns.count(),
        "currently_out": reviewed.filter(status__in=("issued", "partially_returned")).count()
                         + direct.filter(status=PublicToolLoan.Status.CHECKED_OUT).count(),
        "monthly": series(rows, "period", (("issued_count", "loans"), ("return_events", "return events"))),
    }


def machines(space, member):
    from apps.machines.models import MachineUsageEntry

    entries = MachineUsageEntry.objects.filter(machine__makerspace=space, member=member)
    dated = entries.annotate(usage_at=Coalesce("started_at", "created_at", output_field=DateTimeField()))
    monthly = [dict(period=row["period"].date().isoformat(), hours=str(row["hours"])) for row in
               _months(dated, "usage_at", space).values("period").annotate(hours=Sum("hours")).order_by("period")]
    ranked = list(entries.values("machine_id", "machine__name").annotate(hours=Sum("hours")).order_by("-hours", "machine_id"))
    top = [{"machine_id": row["machine_id"], "machine": row["machine__name"], "hours": str(row["hours"])} for row in ranked[:5]]
    if len(ranked) > 5:
        top.append({"machine_id": None, "machine": "Other", "hours": str(sum(row["hours"] for row in ranked[5:]))})
    return {
        "hours": str(entries.aggregate(total=Sum("hours"))["total"] or Decimal(0)),
        "monthly": series(monthly, "period", (("hours", "hours"),)),
        "top_machines": series(top, "machine", (("hours", "hours"),), time=False, top=5),
    }


def bookings(space, member):
    from apps.bookings.models import Booking

    rows = Booking.objects.filter(space__makerspace=space, member=member).exclude(status="cancelled")
    monthly = [{"period": month, "count": count} for month, count in sorted(_counts(rows, "starts_at", space).items())]
    return {"count": rows.count(), "monthly": series(monthly, "period", (("count", "bookings"),))}


def events(space, member):
    from apps.events.models import EventRegistration

    count = EventRegistration.objects.filter(event__makerspace=space, member=member, status="attended").count()
    return {"attended_count": count, "chart": series(
        [{"metric": "attended", "count": count}], "metric", (("count", "events"),), time=False,
    )}


def member_usage(space, member):
    """Called only after the activity membership gate; no staff reports or rankings."""
    result = {}
    if feature_enabled(space, "loans.enabled"):
        result["loans"] = loans(space, member)
    if module_enabled(space, "machines"):
        result["machines"] = machines(space, member)
    if module_enabled(space, "bookings"):
        result["bookings"] = bookings(space, member)
    if module_enabled(space, "events"):
        result["events"] = events(space, member)
    return result


def payment_usage(space, member):
    from apps.payments.models import Payment
    from apps.payments.member_scope import member_payment_queryset

    # This also preserves collaborative-event routing and claim-local restrictions.
    # A pending gift is not owed (payments audit B-7); a paid one still counts as paid.
    payments = member_payment_queryset(member, space.pk).exclude(
        subject_type=Payment.SubjectType.DONATION, status=Payment.Status.PENDING)
    rows = payments.filter(status__in=(Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE, Payment.Status.PENDING)).values(
        "currency", "status",
    ).annotate(total=Sum("amount")).order_by("currency", "status")
    paid, outstanding = {}, {}
    for row in rows:
        target = outstanding if row["status"] == Payment.Status.PENDING else paid
        target[row["currency"]] = str(Decimal(target.get(row["currency"], "0")) + row["total"])
    totals = [{"currency": currency, "paid_total": paid.get(currency, "0"),
               "outstanding_total": outstanding.get(currency, "0")}
              for currency in sorted(paid.keys() | outstanding.keys())]
    return {"paid_by_currency": paid, "outstanding_by_currency": outstanding,
            "totals": series(totals, "currency", (("paid_total", "currency_major"),
                             ("outstanding_total", "currency_major")), time=False, currency="currency")}
