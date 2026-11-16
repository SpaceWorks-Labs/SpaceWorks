"""Scanner, departure, issue, broadcast and pass operations with exact effects."""
from copy import deepcopy
from datetime import timedelta

from apps.bookings.models import Booking
from apps.bookings.models_arrival import BookingCheckInEvent
from apps.bookings.models_departure import BookingDepartureEvent, BookingIssue
from apps.bookings.pass_templates import DEFAULT_PASS_TEMPLATE
from apps.bookings.services_arrival import confirm_arrival, qr_value
from tests.bookings.pass_helpers import pdf_text
from tests.bookings.route_support_cx11b_g1 import Route, equals, fields

CHECKIN = ("bookings", "bookings.confirmations", "bookings.checkin")
PASSES = ("bookings", "bookings.confirmations", "bookings.passes")
BROADCAST = ("bookings", "bookings.broadcasts", "notifications", "email")
ROUTES = (
    Route("admin-booking-arrival-resolve", "POST", CHECKIN, feature_code="not_found"),
    Route("admin-booking-arrival-confirm", "POST", CHECKIN, audit=("booking.arrival_confirmed",), feature_code="not_found"),
    Route("admin-booking-arrival-reverse", "POST", CHECKIN, audit=("booking.arrival_reversed",), feature_code="not_found"),
    Route("admin-booking-arrival-depart", "POST", audit=("booking.departure_recorded",)),
    Route("admin-makerspace-booking-queue"),
    Route("admin-booking-issues"),
    Route("admin-booking-issue-resolve", "POST", audit=("booking.issue_resolved",)),
    Route("admin-booking-broadcasts", keys=BROADCAST),
    Route("admin-booking-broadcasts", "POST", BROADCAST, 201, ("booking.broadcast.created",)),
    Route("admin-booking-broadcast-queue", "POST", BROADCAST, audit=("booking.broadcast.queued",)),
    Route("admin-booking-broadcast-cancel", "POST", BROADCAST, audit=("booking.broadcast.cancelled",)),
    Route("admin-booking-pass-template", keys=PASSES, feature_code="not_found"),
    Route("admin-booking-pass-template", "PUT", PASSES, audit=("booking.pass_template_updated",), feature_code="not_found"),
    Route("admin-booking-pass-preview", "POST", PASSES, audit=("booking.pass_previewed",), feature_code="not_found"),
    Route("admin-booking-pass", "POST", (*CHECKIN, "bookings.passes"), audit=("booking.pass_downloaded",), feature_code="not_found"),
)


def setup(w, monkeypatch):
    name, method = w.route.name, w.route.method
    if "broadcast" in name:
        w.off.update({key: (404, "feature_disabled") for key in ("notifications", "email")})
        return broadcasts(w)
    if "pass" in name:
        return passes(w)
    Booking.objects.filter(pk=w.booking.pk).update(starts_at=w.now - timedelta(minutes=5), ends_at=w.now + timedelta(minutes=55))
    w.booking.refresh_from_db()
    row = w.booking
    if name == "admin-booking-arrival-resolve":
        w.body = {"credential": qr_value(row)}
        w.check = lambda r: equals((r.data["booking_id"], r.data["display_name"], r.data["can_arrive"]),
                                  (row.pk, row.name, True))
    elif name == "admin-booking-arrival-confirm":
        w.body = {"credential": qr_value(row)}
        def arrived(r):
            row.refresh_from_db()
            assert row.arrived_at is not None
            equals(list(BookingCheckInEvent.objects.filter(booking=row).values_list("action", "actor_id")), [("arrived", w.actor.pk)])
            equals(r.data["booking_id"], row.pk)
            assert r.data["arrived_at"] is not None
        w.check = arrived
    elif name == "admin-booking-arrival-reverse":
        confirm_arrival(w.room, qr_value(row), actor=w.actor)
        w.kwargs["booking_id"] = row.pk
        def reversed_arrival(r):
            fields(row, arrived_at=None)
            equals(list(BookingCheckInEvent.objects.filter(booking=row).order_by("pk").values_list("action", flat=True)), ["arrived", "reversed"])
            equals(r.data["arrived_at"], None)
        w.check = reversed_arrival
    elif name == "admin-booking-arrival-depart":
        w.kwargs["booking_id"] = row.pk
        # Deliberately ONLY the departure serializer's fields (review finding 3).
        w.body = {"outcome": "damaged", "remark": "G1 damaged door handle Δ"}
        def departed(r):
            event = BookingDepartureEvent.objects.get(booking=row)
            fields(event, outcome="damaged", remark=w.body["remark"], source="staff", actor_id=w.actor.pk)
            equals(BookingIssue.objects.filter(booking=row, departure=event, outcome="damaged").count(), 1)
            row.refresh_from_db()
            assert row.departed_at is not None
        w.check = departed
    elif name == "admin-makerspace-booking-queue":
        w.kwargs = {"makerspace_id": w.tenant.pk}
        w.body = {"status": "confirmed"}
        w.check = lambda r: equals([(x["id"], x["status"]) for x in r.data["results"]], [(row.pk, "confirmed")])
    else:
        from apps.bookings.services_departure import record_departure
        if name == "admin-booking-issue-resolve":
            w.off["bookings"] = (404, "not_found")
        record_departure(row, actor=w.actor, outcome="damaged", remark="Retained broken handle")
        issue = BookingIssue.objects.get(booking=row)
        if name == "admin-booking-issues":
            w.kwargs = {"makerspace_id": w.tenant.pk}
            w.check = lambda r: equals((r.data["open_count"], [(x["id"], x["remark"]) for x in r.data["results"]]),
                                       (1, [(issue.pk, "Retained broken handle")]))
        else:
            w.kwargs = {"pk": issue.pk}
            w.body = {"note": "G1 repaired handle"}
            def resolved(r):
                fields(issue, resolution_note=w.body["note"], resolved_by_id=w.actor.pk)
                assert issue.resolved_at is not None
                equals(BookingDepartureEvent.objects.get(booking=row).remark, "Retained broken handle")
            w.check = resolved


def broadcasts(w):
    from apps.bookings.models_broadcasts import BookingBroadcast
    from apps.bookings.services_broadcasts import compose
    values = {"subject": "Retained G1 broadcast", "body": "Please meet at the studio.",
        "window_start": w.start - timedelta(days=1), "window_end": w.start + timedelta(days=2), "statuses": ["confirmed"]}
    campaign = compose(w.room, w.actor, **values)
    name, method = w.route.name, w.route.method
    if name == "admin-booking-broadcasts" and method == "GET":
        w.check = lambda r: equals([(x["id"], x["subject"], x["status"]) for x in r.data["results"]],
                                   [(campaign.pk, values["subject"], "draft")])
    elif name == "admin-booking-broadcasts":
        w.body = {**values, "subject": "G1 newly composed", "window_start": values["window_start"].isoformat(),
                  "window_end": values["window_end"].isoformat()}
        def composed(r):
            equals(BookingBroadcast.objects.filter(space=w.room).count(), 2)
            fields(BookingBroadcast.objects.get(pk=r.data["id"]), subject=w.body["subject"], body=w.body["body"], status="draft")
        w.check = composed
    else:
        w.kwargs["campaign_id"] = campaign.pk
        target = "queued" if name.endswith("queue") else "cancelled"
        def changed(r):
            fields(campaign, status=target, subject=values["subject"])
            assert (campaign.queued_at if target == "queued" else campaign.completed_at) is not None
            equals(BookingBroadcast.objects.filter(space=w.room).count(), 1)
        w.check = changed


def passes(w):
    name, method = w.route.name, w.route.method
    template = deepcopy(DEFAULT_PASS_TEMPLATE)
    template["orientation"] = "landscape"
    if name == "admin-booking-pass-template" and method == "GET":
        w.check = lambda r: equals(r.data, DEFAULT_PASS_TEMPLATE)
    elif name == "admin-booking-pass-template":
        w.body = template
        def saved(r):
            equals(r.data, template)
            fields(w.room, pass_template=template)
        w.check = saved
    elif name == "admin-booking-pass-preview":
        w.body = template
        def preview(r):
            equals(r["Content-Type"], "application/pdf")
            assert "Sample booker" in pdf_text(r.content)
            assert w.booking.note not in pdf_text(r.content)
        w.check = preview
    else:
        Booking.objects.filter(pk=w.booking.pk).update(starts_at=w.now - timedelta(minutes=5), ends_at=w.now + timedelta(minutes=55))
        w.booking.refresh_from_db()
        confirm_arrival(w.room, qr_value(w.booking), actor=w.actor)
        w.kwargs["booking_id"] = w.booking.pk
        def printed(r):
            equals(r["Content-Type"], "application/pdf")
            text = pdf_text(r.content)
            assert w.booking.name in text
            assert f"Booking #{w.booking.pk}" in text
            assert w.booking.note not in text
        w.check = printed
