"""Issue cohorts and event-time loan measurements; no holder data in totals."""

from collections import defaultdict

from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem, ReturnEvent
from apps.hardware_requests.models import HardwareRequestItemAsset
from apps.operations.reports_ab_common import (
    bucket, dated, histogram, hours, result, spaces,
)


MOST_FIELDS = ("period", "product_id", "product_name", "times_lent", "total_quantity_lent")
THROUGHPUT_FIELDS = ("period", "issued_requests", "issued_units", "return_events", "returned_units",
                     "return_quantity_unknown_events", "closures_with_loss", "lost_units")
FUNNEL_FIELDS = ("period", "row_kind", "stage", "approval_bucket", "count")


def build_most_lent(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in spaces(makerspace_id, "request_workflow"):
        groups = {}
        seen = defaultdict(set)
        totals = defaultdict(int)
        qs = dated(HardwareRequestItem.objects.filter(request__makerspace=space, issued_quantity__gt=0),
                   "request__issued_at", space, date_range, grain).select_related("product")
        for item in qs.iterator():
            # Legacy issued rows may lack issued_at. Keep their unbounded export
            # totals in an unknown cohort rather than inventing a date or crashing.
            key = (item.report_period.date() if item.report_period else None, item.product_id)
            row = groups.setdefault(key, dict(makerspace_id=space.pk, period=key[0], product_id=item.product_id,
                                             product_name=item.product.name, times_lent=0, total_quantity_lent=0))
            seen[key].add(item.request_id)
            row["times_lent"] = len(seen[key])
            row["total_quantity_lent"] += item.issued_quantity
            totals[item.product_id] += item.issued_quantity
        top = set(sorted(totals, key=lambda pk: (-totals[pk], pk))[:5])
        # Keep an explicit Other series; no quantity disappears in a truncated chart.
        other = {}
        for row in groups.values():
            if row["product_id"] in top:
                records.append(row)
            else:
                target = other.setdefault(row["period"], dict(row, product_id=None, product_name="Other",
                                                            times_lent=0, total_quantity_lent=0))
                for field in ("times_lent", "total_quantity_lent"):
                    target[field] += row[field]
        records.extend(other.values())
    records.sort(key=lambda row: (row["period"] is None, row["period"],
                                  -row["total_quantity_lent"], row["product_name"]))
    return result(MOST_FIELDS, records, makerspace_id, limit)


def build_loan_throughput(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in spaces(makerspace_id, "request_workflow"):
        groups = {}

        def row(at):
            period = bucket(at, space, grain)
            return groups.setdefault(period, dict.fromkeys(THROUGHPUT_FIELDS[1:], 0) |
                                     {"period": period, "makerspace_id": space.pk})

        requests = HardwareRequest.objects.filter(makerspace=space)
        for request in dated(requests.filter(issued_at__isnull=False), "issued_at", space, date_range, grain
                             ).prefetch_related("items").iterator(chunk_size=200):
            target = row(request.issued_at)
            target["issued_requests"] += 1
            target["issued_units"] += sum(item.issued_quantity for item in request.items.all())
        # ReturnEvent has no bulk quantity column. Asset links carry exact per-event quantities;
        # bulk returns with multiple events cannot be assigned from cumulative item counters.
        events = dated(ReturnEvent.objects.filter(makerspace=space), "created_at", space, date_range, grain)
        from django.db.models import Count
        # Count every event for selected requests, including earlier partial returns.
        # Unrelated historical requests must never be materialized for this window.
        counts = dict(ReturnEvent.objects.filter(
            makerspace=space, request_id__in=events.values("request_id"),
        ).values("request_id").annotate(n=Count("pk")).values_list("request_id", "n"))
        linked = defaultdict(int)
        for event_id in HardwareRequestItemAsset.objects.filter(
            request_item__request__makerspace=space, outcome="returned", return_event__in=events,
        ).values_list("return_event_id", flat=True):
            linked[event_id] += 1
        for event in events.select_related("request").prefetch_related("request__items__product").iterator(chunk_size=200):
            target = row(event.created_at)
            target["return_events"] += 1
            items = list(event.request.items.all())
            bulk = [item for item in items if item.product.tracking_mode != "individual"]
            if counts[event.request_id] == 1:
                target["returned_units"] += sum(item.returned_quantity for item in items)
            else:
                target["returned_units"] += linked[event.pk]
                if bulk:
                    target["return_quantity_unknown_events"] += 1
        for request in dated(requests.filter(closed_at__isnull=False, items__missing_quantity__gt=0).distinct(),
                             "closed_at", space, date_range, grain).prefetch_related("items").iterator(chunk_size=200):
            target = row(request.closed_at)
            target["closures_with_loss"] += 1
            target["lost_units"] += sum(item.missing_quantity for item in request.items.all())
        records.extend(groups.values())
    return result(THROUGHPUT_FIELDS, sorted(records, key=lambda row: row["period"]), makerspace_id, limit,
        meta={"basis": "Issue time, ReturnEvent time and loss closure time are independent series.",
              "limitations": "Multiple bulk return events have no recorded per-event quantities; unknown events are counted separately."})


def build_request_funnel(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in spaces(makerspace_id, "request_workflow"):
        groups = defaultdict(int)
        for request in dated(HardwareRequest.objects.filter(makerspace=space).exclude(status="draft"),
                             "created_at", space, date_range, grain).iterator():
            period = request.report_period.date()
            for stage, qualifies in (("requested", True), ("accepted", request.accepted_at),
                                     ("issued", request.issued_at), ("returned", request.status == "returned")):
                if qualifies:
                    groups[(period, "funnel", stage, "")] += 1
            if request.accepted_at:
                groups[(period, "approval_histogram", "accepted",
                        histogram(hours(request.created_at, request.accepted_at)))] += 1
        records.extend(dict(makerspace_id=space.pk, period=p, row_kind=k, stage=s, approval_bucket=b, count=n)
                       for (p, k, s, b), n in sorted(groups.items()))
    return result(FUNNEL_FIELDS, records, makerspace_id, limit)
