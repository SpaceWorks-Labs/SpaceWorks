"""Exact seeded booking results and complete operation audit deltas."""
from datetime import datetime, timedelta
from io import BytesIO

from PIL import Image
from apps.bookings.models import Booking, BookableSpace
from apps.bookings.models_arrival import BookingCheckInEvent
from apps.bookings.models_departure import BookingDepartureEvent
from apps.bookings.models_gallery import BookableSpacePhoto
from apps.bookings.models_organization import BookingOrganizationLink
from apps.bookings.pass_templates import normalize_pass_template
from tests.bookings.pass_helpers import pdf_text
from tests.bookings.route_support_cx11b_g1 import fields


TRANSITIONS = {
    "approve": ("confirmed", ["booking.approved", "booking.price_quoted_at_approval"]),
    "reject": ("rejected", ["booking.rejected"]), "cancel": ("cancelled", ["booking.cancelled"]),
    "complete": ("completed", ["booking.completed"]), "no-show": ("no_show", ["booking.no_show_marked"]),
    "restore": ("confirmed", ["booking.restored"]),
}


def booking_result(op, body, o, response):
    name, data = op.name, getattr(response, "data", None)
    row, room = o["booking"], o["room"]
    if name in {"admin-booking-" + edge for edge in TRANSITIONS}:
        edge = name.removeprefix("admin-booking-")
        target, actions = TRANSITIONS[edge]
        fields(row, status=target)
        assert data["id"] == row.pk
        if edge == "reject":
            fields(row, decision_reason=body["reason"])
        return actions
    if name == "admin-booking-details-edit":
        fields(row, note=body["note"])
        return ["booking.details_edited"]
    if name == "admin-booking-time-edit":
        fields(row, starts_at=datetime.fromisoformat(body["starts_at"]), ends_at=datetime.fromisoformat(body["ends_at"]))
        return ["booking.rescheduled"]
    if name == "admin-booking-readiness":
        assert data == {"ready": True, "checks": [{"code": "room_outage", "state": "ok",
            "detail": "No room outage blocks this time."}], "maintenance_link": None}
        return []
    if name == "admin-bookable-space-clone":
        clone = BookableSpace.objects.get(pk=data["id"])
        fields(clone, name=room.name + " (copy)", is_public=False, is_active=True)
        assert clone.pk != room.pk and Booking.objects.filter(space=clone).count() == 0
        assert BookableSpace.objects.filter(makerspace=room.makerspace).count() == 2
        return ["booking.space_cloned"]
    if name == "admin-space-booking-list":
        assert [(r["id"], r["name"]) for r in data["results"]] == [(row.pk, row.name)]
        return []
    if name.endswith("arrival-resolve"):
        assert (data["booking_id"], data["display_name"], data["can_arrive"]) == (row.pk, row.name, True)
        return []
    if name.endswith(("arrival-confirm", "arrival-reverse")):
        reverse = name.endswith("reverse")
        row.refresh_from_db()
        assert (row.arrived_at is None) is reverse
        assert list(BookingCheckInEvent.objects.filter(booking=row).order_by("pk").values_list("action", flat=True)) == (
            ["arrived", "reversed"] if reverse else ["arrived"])
        return ["booking.arrival_reversed" if reverse else "booking.arrival_confirmed"]
    if name.endswith("arrival-depart"):
        event = BookingDepartureEvent.objects.get(booking=row)
        fields(event, outcome="all_good", remark=body["remark"], source="staff")
        row.refresh_from_db()
        assert row.departed_at is not None
        return ["booking.departure_recorded"]
    if name == "admin-booking-issue-resolve":
        issue = o["issue"]
        fields(issue, resolution_note=body["note"])
        assert issue.resolved_at is not None and issue.resolved_by_id is not None
        return ["booking.issue_resolved"]
    if name in {"admin-bookable-space-photos", "admin-bookable-space-photo-order"}:
        photos = list(BookableSpacePhoto.objects.filter(space=room).values_list("pk", "position"))
        expected = body["order"] if name.endswith("photo-order") else [o["photo_one"].pk, o["photo_two"].pk]
        assert photos == list(zip(expected, [1, 2]))
        results = data["results"] if isinstance(data, dict) else data
        assert [r["id"] for r in results] == expected
        return ["booking.space_photos_reordered"] if name.endswith("photo-order") else []
    if name == "admin-booking-pass-template":
        expected = normalize_pass_template(body if op.method == "PUT" else None)
        assert data == expected
        if op.method == "PUT":
            fields(room, pass_template=expected)
        return ["booking.pass_template_updated"] if op.method == "PUT" else []
    if name in {"admin-booking-pass-preview", "admin-booking-pass"}:
        assert response["Content-Type"] == "application/pdf"
        text = pdf_text(response.content)
        assert ("Sample booker" if name.endswith("preview") else row.name) in text
        if not name.endswith("preview"):
            assert f"Booking #{row.pk}" in text
        return ["booking.pass_previewed" if name.endswith("preview") else "booking.pass_downloaded"]
    if name == "member-booking-confirmation":
        from apps.bookings.services_arrival import qr_value
        assert (str(data["public_token"]), data["space_name"], data["qr_value"]) == (
            str(row.public_token), room.name, qr_value(row))
        return []
    if name == "member-booking-confirmation-png":
        assert response["Content-Type"] == "image/png"
        with Image.open(BytesIO(response.content)) as png:
            assert png.format == "PNG" and png.width > 100 and png.height > 100
            assert png.convert("RGB").getextrema() != ((255, 255),) * 3
        return ["booking.confirmation_downloaded"]
    if name == "member-booking-calendar":
        assert str(row.public_token).encode() in response.content
        assert room.name.encode() in response.content
        return ["booking.calendar_downloaded"]
    if name == "admin-recurring-bookings":
        created = list(Booking.objects.filter(space=room).exclude(pk=row.pk).order_by("starts_at"))
        start = datetime.fromisoformat(body["starts_at"])
        end = datetime.fromisoformat(body["ends_at"])
        assert [(r.member_id, r.starts_at, r.ends_at, r.status) for r in created] == [
            (o["booker"].pk, start + timedelta(days=d), end + timedelta(days=d), "confirmed") for d in (0, 7)]
        assert [(r["booking_id"], r["status"]) for r in data["occurrences"]] == [(r.pk, "confirmed") for r in created]
        return ["booking.created", "booking.created", "booking.recurrence_created"]
    if name == "admin-space-organization-booking-choices":
        assert data == [{"organization_id": o["organization"].pk, "name": o["organization"].name,
            "contacts": [{"member_id": o["booker"].pk, "name": o["booker"].display_name or o["booker"].username}]}]
        return []
    if name == "admin-space-organization-booking":
        created = Booking.objects.get(pk=data["id"])
        fields(created, member_id=o["booker"].pk, starts_at=datetime.fromisoformat(body["starts_at"]), status="confirmed")
        link = BookingOrganizationLink.objects.get(booking=created)
        fields(link, organization_id=o["organization"].pk, billed_member_id=o["booker"].pk)
        return ["booking.organization_linked", "booking.created"]
    if "staff-grant" in name or "staff-invite" in name:
        target = o[op.target]
        target.refresh_from_db()
        if name.endswith("detail"):
            assert target.permissions == ["check_in"]
            return ["booking.staff_grant_updated"]
        assert target.revoked_at is not None
        return ["booking.staff_grant_invite_revoked" if "invite" in name else "booking.staff_grant_revoked"]
    if "broadcast" in name:
        from apps.bookings.models_broadcasts import BookingBroadcast
        if op.method == "GET":
            assert [(r["id"], r["subject"]) for r in data["results"]] == [(o["campaign"].pk, "Workshop arrangements")]
            return []
        campaign = BookingBroadcast.objects.get(pk=data["id"])
        target = "draft" if name.endswith("broadcasts") else "queued" if name.endswith("queue") else "cancelled"
        fields(campaign, subject="Workshop arrangements", status=target)
        assert BookingBroadcast.objects.filter(space=room).count() == (2 if name.endswith("broadcasts") else 1)
        return ["booking.broadcast." + {"draft": "created", "queued": "queued", "cancelled": "cancelled"}[target]]
    raise AssertionError((name, "Missing operation-specific result proof"))
