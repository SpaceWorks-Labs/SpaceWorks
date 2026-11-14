"""Concrete room/booking commands and seeded staff projections (481/494/520)."""
from datetime import timedelta

from apps.bookings.models import BookableSpace, Booking
from tests.bookings.route_support_cx11b_g1 import Route, equals, fields, window

ROUTES = (
    Route("admin-bookable-space-list-create"),
    Route("admin-bookable-space-list-create", "POST", status=201, audit=("booking.space_created",)),
    Route("admin-bookable-space-detail"),
    Route("admin-bookable-space-detail", "PATCH", audit=("booking.space_updated",)),
    Route("admin-bookable-space-deactivate", "POST", audit=("booking.space_deactivated",)),
    Route("admin-bookable-space-clone", "POST", ("bookings", "bookings.clone"), 201, ("booking.space_cloned",)),
    Route("admin-bookable-space-booking-rules"),
    Route("admin-bookable-space-booking-rules", "PATCH", audit=("booking.space_rules_updated",)),
    Route("admin-space-booking-list"),
    Route("admin-space-booking-list", "POST", status=201, audit=("booking.created",)),
    Route("admin-space-booking-eligible-members"),
    Route("admin-space-booking-quote", "POST", ("bookings", "charges.enabled", "charges.bookings", "charges.pricing")),
    Route("admin-space-booking-readiness", keys=("bookings", "bookings.room_maintenance")),
    Route("admin-space-booking-availability"),
    Route("admin-booking-readiness", keys=("bookings", "bookings.room_maintenance")),
    Route("admin-booking-machine-types", keys=("bookings", "machines")),
    Route("admin-booking-details-edit", "PATCH", ("bookings", "bookings.staff_tools"), audit=("booking.details_edited",)),
    Route("admin-booking-time-edit", "POST", ("bookings", "bookings.staff_tools"), audit=("booking.rescheduled",)),
    Route("admin-booking-restore", "POST", ("bookings", "bookings.staff_tools"), audit=("booking.restored",)),
    Route("admin-booking-approve", "POST", audit=("booking.approved", "booking.price_quoted_at_approval")),
    Route("admin-booking-reject", "POST", audit=("booking.rejected",)),
    Route("admin-booking-cancel", "POST", audit=("booking.cancelled",)),
    Route("admin-booking-complete", "POST", audit=("booking.completed",)),
    Route("admin-booking-no-show", "POST", audit=("booking.no_show_marked",)),
    Route("admin-recurring-bookings", "POST", ("bookings", "bookings.recurring"),
          audit=("booking.created", "booking.created", "booking.recurrence_created")),
)


def setup(w, monkeypatch):
    name, method = w.route.name, w.route.method
    room, row = w.room, w.booking
    if name == "admin-bookable-space-list-create":
        w.kwargs = {"makerspace_id": w.tenant.pk}
        if method == "GET":
            w.check = lambda r: equals([(x["id"], x["name"]) for x in r.data["results"]], [(room.pk, room.name)])
        else:
            w.body = {"name": "New G1 meeting room", "kind": "meeting", "capacity": 8}
            def created(r):
                equals(BookableSpace.objects.filter(makerspace=w.tenant).count(), 2)
                fields(BookableSpace.objects.get(pk=r.data["id"]), name=w.body["name"], kind="meeting", capacity=8)
            w.check = created
    elif name == "admin-bookable-space-detail":
        if method == "GET":
            w.check = lambda r: equals((r.data["id"], r.data["name"]), (room.pk, room.name))
        else:
            w.body = {"description": "Studio Δ — updated", "capacity": 6}
            w.check = lambda r: fields(room, description=w.body["description"], capacity=6)
    elif name == "admin-bookable-space-deactivate":
        w.check = lambda r: fields(room, is_active=False)
    elif name == "admin-bookable-space-clone":
        w.body = {"copy_booking_rules": True}
        def cloned(r):
            equals(BookableSpace.objects.filter(makerspace=w.tenant).count(), 2)
            clone = BookableSpace.objects.get(pk=r.data["id"])
            fields(clone, name=room.name + " (copy)", is_public=False, is_active=True,
                   booking_lead_time_minutes=room.booking_lead_time_minutes)
            equals(Booking.objects.filter(space=clone).count(), 0)
            equals(Booking.objects.filter(space=room).count(), 1)
        w.check = cloned
    elif name == "admin-bookable-space-booking-rules":
        w.body = {"booking_lead_time_minutes": 90} if method == "PATCH" else {}
        w.check = (lambda r: fields(room, booking_lead_time_minutes=90)) if method == "PATCH" else (
            lambda r: equals(r.data["booking_lead_time_minutes"], 60))
    elif name == "admin-space-booking-list":
        if method == "GET":
            w.check = lambda r: equals([(x["id"], x["note"]) for x in r.data["results"]], [(row.pk, row.note)])
        else:
            w.body = {**window(w), "member_id": w.member.pk, "note": "Created through G1 route"}
            def created(r):
                equals(Booking.objects.filter(space=room).count(), 2)
                fields(Booking.objects.get(pk=r.data["id"]), space_id=room.pk, member_id=w.member.pk,
                       starts_at=w.start + timedelta(days=1), status="confirmed", note=w.body["note"])
            w.check = created
    elif name == "admin-space-booking-eligible-members":
        w.check = lambda r: equals([(x["member_id"], x["display_name"]) for x in r.data["results"]],
                                   [(w.member.pk, w.member.display_name or w.member.username)])
    elif name == "admin-space-booking-quote":
        from tests.payments.pricing.helpers import rate
        BookableSpace.objects.filter(pk=room.pk).update(payment_amount="12.00")
        rate(w.tenant, "bookings", per_booking="0.00", per_hour="7.00")
        w.body = {**window(w), "member_id": w.member.pk}
        def quote(r):
            equals(r.data["charges"], "tracked")
            equals((r.data["quote"]["total"], r.data["quote"]["currency"]), ("19.00", "usd"))
            equals(len(r.data["price_confirmation"]), 64)
        w.check = quote
        w.off.update({key: (200, None) for key in ("charges.enabled", "charges.bookings", "charges.pricing")})
        def price_policy(key, r):
            if key == "charges.pricing":
                equals((r.data["charges"], r.data["quote"]["total"]), ("tracked", "12.00"))
            else:
                equals((r.data["charges"], r.data["quote"]), ("off", None))
        w.policy_off = price_policy
    elif name in {"admin-space-booking-readiness", "admin-booking-readiness"}:
        if name == "admin-booking-readiness":
            w.kwargs = {"pk": row.pk}
        else:
            w.body = {**window(w), "member_id": w.member.pk}
        expected = {"ready": True, "checks": [{"code": "room_outage", "state": "ok",
                    "detail": "No room outage blocks this time."}], "maintenance_link": None}
        w.check = lambda r: equals(r.data, expected)
        w.off["bookings.room_maintenance"] = (200, None)
        w.policy_off = lambda key, r: equals(r.data, {"ready": True, "checks": [], "maintenance_link": None})
    elif name == "admin-space-booking-availability":
        w.body = window(w, moved=False)
        def busy(r):
            equals(r.data["space_id"], room.pk)
            equals([x["booking_id"] for x in r.data["busy"]], [row.pk])
            equals(r.data["requested"]["conflict"], True)
        w.check = busy
    elif name == "admin-booking-machine-types":
        from apps.machines.models import MachineType
        kind = MachineType.objects.create(makerspace=w.tenant, name="G1 retained laser", slug="g1-retained-laser")
        w.kwargs = {"makerspace_id": w.tenant.pk}
        w.check = lambda r: equals([(x["id"], x["name"]) for x in r.data["results"] if x["id"] == kind.pk],
                                   [(kind.pk, kind.name)])
    elif name == "admin-recurring-bookings":
        w.body = {**window(w), "member_id": w.member.pk, "count": 2}
        def recurrence(r):
            equals([x["status"] for x in r.data["occurrences"]], ["confirmed", "confirmed"])
            rows = list(Booking.objects.filter(space=room).exclude(pk=row.pk).order_by("starts_at"))
            equals([(x.member_id, x.starts_at, x.ends_at) for x in rows], [
                (w.member.pk, w.start + timedelta(days=days), w.start + timedelta(days=days, hours=1)) for days in (1, 8)])
            equals([x["booking_id"] for x in r.data["occurrences"]], [x.pk for x in rows])
        w.check = recurrence
    else:
        setup_booking(w)


def setup_booking(w):
    name, row = w.route.name, w.booking
    w.kwargs = {"pk": row.pk}
    if name == "admin-booking-details-edit":
        w.body = {"note": "G1 changed note Δ"}
        w.check = lambda r: fields(row, note=w.body["note"])
    elif name == "admin-booking-time-edit":
        old_token = row.checkin_token
        w.body = window(w)
        def moved(r):
            fields(row, starts_at=w.start + timedelta(days=1), ends_at=w.start + timedelta(days=1, hours=1),
                   member_id=w.member.pk, note="Retained private note", status="confirmed")
            assert row.checkin_token != old_token
        w.check = moved
    elif name == "admin-booking-restore":
        from apps.bookings.services_transitions import cancel_booking
        cancel_booking(row, actor=w.actor)
        w.check = lambda r: fields(row, status="confirmed", decision_reason="")
    else:
        target = {"admin-booking-approve": "confirmed", "admin-booking-reject": "rejected",
            "admin-booking-cancel": "cancelled", "admin-booking-complete": "completed", "admin-booking-no-show": "no_show"}[name]
        if name in {"admin-booking-approve", "admin-booking-reject"}:
            Booking.objects.filter(pk=row.pk).update(status="pending")
        if name in {"admin-booking-complete", "admin-booking-no-show"}:
            Booking.objects.filter(pk=row.pk).update(starts_at=w.now - timedelta(hours=2), ends_at=w.now - timedelta(hours=1))
        if name == "admin-booking-reject":
            w.body = {"reason": "G1 rejection reason"}
        def transitioned(r):
            fields(row, status=target)
            equals(r.data["id"], row.pk)
            if name == "admin-booking-reject":
                fields(row, decision_reason=w.body["reason"])
        w.check = transitioned
