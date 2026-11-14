"""Owner, public and revocable bearer routes; contracts are per route, never blanket."""
from datetime import timedelta
from io import BytesIO

from django.urls import reverse
from icalendar import Calendar
from PIL import Image
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.bookings.models_departure import BookingDepartureEvent, BookingIssue
from apps.bookings.models_feed import BookingCalendarFeed
from apps.bookings.services_arrival import qr_value
from apps.bookings.views_feed import digest
from tests.bookings.pass_helpers import pdf_text
from tests.bookings.route_support_cx11b_g1 import Route, equals, fields, person_client, window
from tests.modules.switch_matrix_object_helpers import client_for

CONFIRM = ("bookings", "bookings.confirmations")
FEED = ("bookings", "bookings.calendar_feed")
ROUTES = (
    Route("member-booking-confirmation", keys=(*CONFIRM, "bookings.checkin", "bookings.passes"), feature_code="not_found", standing="owner"),
    Route("member-booking-confirmation-png", keys=(*CONFIRM, "bookings.checkin"), audit=("booking.confirmation_downloaded",), feature_code="not_found", standing="owner"),
    Route("member-booking-calendar", keys=CONFIRM, audit=("booking.calendar_downloaded",), feature_code="not_found", standing="owner"),
    Route("member-booking-rotate-checkin", "POST", (*CONFIRM, "bookings.checkin"), audit=("booking.checkin_credential_rotated",), feature_code="not_found", standing="owner"),
    Route("member-booking-pass", keys=(*CONFIRM, "bookings.passes"), audit=("booking.pass_downloaded",), feature_code="not_found", standing="owner"),
    Route("member-booking-list", standing="personal-list"),
    Route("member-booking-cancel", "POST", audit=("booking.cancelled",), standing="owner"),
    Route("member-booking-reschedule", "POST", audit=("booking.rescheduled",), standing="owner"),
    Route("member-booking-checkout", "POST", audit=("booking.departure_recorded",), standing="owner"),
    Route("member-booking-feed-settings", keys=FEED, standing="personal-list"),
    Route("member-booking-feed-settings", "POST", FEED, audit=("booking.feed_rotated",), standing="account"),
    Route("member-booking-feed-settings", "DELETE", FEED, 204, ("booking.feed_revoked",), standing="account"),
    Route("public-booking-feed", keys=FEED, standing="bearer"),
    Route("public-bookable-space-list", standing="public"),
    Route("public-space-availability", standing="public"),
    Route("public-booking-submit", "POST", status=201, audit=("booking.created",), standing="account"),
    Route("public-event-venue", keys=("events", "bookings"), standing="public"),
)


def calendar_check(w, response):
    events = Calendar.from_ical(response.content).walk("VEVENT")
    equals(len(events), 1)
    equals(events[0]["DTSTART"].dt, w.booking.starts_at)
    assert w.room.name in str(events[0]["SUMMARY"])
    assert w.booking.note.encode() not in response.content


def setup(w, monkeypatch):
    name, method = w.route.name, w.route.method
    if "feed" in name:
        return feeds(w)
    staff_client = w.client
    w.client = person_client(w.member, w.tenant, w.native)
    w.kwargs = {"makerspace_slug": w.tenant.slug, "public_token": w.booking.public_token}
    if name == "member-booking-list":
        w.kwargs.pop("public_token")
        w.foreign_pair = (200, None)
        w.foreign_check = lambda r: equals(r.data["results"], [])
        w.foreign_off["bookings"] = (404, "module_disabled")
        w.check = lambda r: equals([(str(x["public_token"]), x["space_name"]) for x in r.data["results"]],
                                   [(str(w.booking.public_token), w.room.name)])
    elif name == "member-booking-confirmation":
        def confirmed(r):
            equals((str(r.data["public_token"]), r.data["space_name"], r.data["qr_value"]),
                (str(w.booking.public_token), w.room.name, qr_value(w.booking)))
            equals(r.data["pass_available"], True)
        w.check = confirmed
        w.off.update({"bookings.checkin": (200, None), "bookings.passes": (200, None)})
        def projection_off(key, r):
            equals(str(r.data["public_token"]), str(w.booking.public_token))
            equals(r.data["qr_value"], None if key == "bookings.checkin" else qr_value(w.booking))
            equals(r.data["pass_available"], key != "bookings.passes")
        w.policy_off = projection_off
    elif name == "member-booking-confirmation-png":
        from apps.bookings import confirmation_render
        render = confirmation_render.render_confirmation_png
        w.io, w.png_count = [], 0
        def render_recorded(**values):
            w.io.append(values)
            return render(**values)
        monkeypatch.setattr(confirmation_render, "render_confirmation_png", render_recorded)
        def png(r):
            equals(len(w.io), w.png_count + 1)
            w.png_count += 1
            equals((w.io[-1]["qr_value"], w.io[-1]["title"]), (qr_value(w.booking), w.room.name))
            equals(r["Content-Type"], "image/png")
            with Image.open(BytesIO(r.content)) as result:
                equals(result.format, "PNG")
                assert result.width > 100 and result.height > 100
        w.check = png
    elif name == "member-booking-calendar":
        w.check = lambda r: calendar_check(w, r)
    elif name == "member-booking-rotate-checkin":
        token = w.booking.checkin_token
        def rotated(r):
            w.booking.refresh_from_db()
            assert w.booking.checkin_token != token
            equals(r.data["qr_value"], qr_value(w.booking))
        w.check = rotated
    elif name == "member-booking-pass":
        def pdf(r):
            equals(r["Content-Type"], "application/pdf")
            assert w.booking.name in pdf_text(r.content)
            assert f"Booking #{w.booking.pk}" in pdf_text(r.content)
        w.check = pdf
    elif name == "member-booking-cancel":
        w.check = lambda r: fields(w.booking, status="cancelled", member_id=w.member.pk)
    elif name == "member-booking-reschedule":
        w.body = window(w)
        w.check = lambda r: fields(w.booking, starts_at=w.start + timedelta(days=1),
                                   ends_at=w.start + timedelta(days=1, hours=1), member_id=w.member.pk)
    elif name == "member-booking-checkout":
        Booking.objects.filter(pk=w.booking.pk).update(starts_at=w.now - timedelta(minutes=5), ends_at=w.now + timedelta(minutes=55))
        w.body = {"outcome": "all_good", "remark": "G1 owner checkout Δ"}
        def departed(r):
            event = BookingDepartureEvent.objects.get(booking=w.booking)
            fields(event, outcome="all_good", remark=w.body["remark"], source="member", actor_id=w.member.pk)
            equals(BookingIssue.objects.filter(booking=w.booking).count(), 0)
        w.check = departed
    else:
        public(w)
    if w.route.standing == "owner":
        # Same-space non-owner as well as a foreign account (520).
        w.same = staff_client


def feeds(w):
    raw = "g" * 43
    feed = BookingCalendarFeed.objects.create(makerspace=w.tenant, user=w.member,
        token_digest=digest(raw), token_hint=raw[-8:])
    w.client = person_client(w.member, w.tenant, w.native)
    w.kwargs = {"makerspace_slug": w.tenant.slug}
    method = w.route.method
    if w.route.name == "public-booking-feed":
        w.kwargs["raw_token"] = raw
        w.foreign_url = reverse(w.route.name, kwargs={**w.kwargs, "raw_token": "z" * 43})
        # A bearer URL needs no account. Invalid tokens retain this route's gate-first contract.
        w.foreign_off = {"bookings": (404, "module_disabled"), "bookings.calendar_feed": (404, "feature_disabled")}
        w.check = lambda r: calendar_check(w, r)
    elif method == "GET":
        w.foreign_pair = (200, None)
        w.foreign_off = {"bookings": (404, "module_disabled"), "bookings.calendar_feed": (404, "feature_disabled")}
        w.foreign_check = lambda r: equals(r.data, {"enabled": False, "token_hint": None})
        w.check = lambda r: equals(r.data, {"enabled": True, "token_hint": raw[-8:]})
    else:
        w.foreign = APIClient()
        w.foreign_pair = (401, "not_authenticated")
        if method == "POST":
            def rotated(r):
                token = r.data["feed_url"].rsplit("/", 1)[-1].removesuffix(".ics")
                feed.refresh_from_db()
                equals(bytes(feed.token_digest), digest(token))
                assert token != raw
                equals(feed.token_hint, token[-8:])
                equals(BookingCalendarFeed.objects.filter(user=w.member, makerspace=w.tenant).count(), 1)
            w.check = rotated
        else:
            def revoked(r):
                feed.refresh_from_db()
                assert feed.revoked_at is not None
                equals(bytes(feed.token_digest), digest(raw))
            w.check = revoked


def public(w):
    name = w.route.name
    w.kwargs = {"makerspace_slug": w.tenant.slug, "public_token": w.room.public_token}
    w.foreign_pair = (200, None)
    if name == "public-bookable-space-list":
        w.kwargs.pop("public_token")
        w.check = lambda r: equals([(str(x["public_token"]), x["name"]) for x in r.data], [(str(w.room.public_token), w.room.name)])
    elif name == "public-space-availability":
        w.body = window(w, moved=False)
        def occupied(r):
            from django.utils.dateparse import parse_datetime
            equals([(parse_datetime(x["starts_at"]), parse_datetime(x["ends_at"]), x["booker_name"], x["tentative"])
                   for x in r.data["availability"]], [(w.start, w.start + timedelta(hours=1), None, False)])
        w.check = occupied
    elif name == "public-booking-submit":
        w.body = window(w)
        w.foreign, w.foreign_pair = APIClient(), (401, "not_authenticated")
        def created(r):
            equals(Booking.objects.filter(space=w.room).count(), 2)
            row = Booking.objects.get(public_token=r.data["public_token"])
            fields(row, member_id=w.member.pk, status="confirmed", starts_at=w.start + timedelta(days=1))
        w.check = created
    else:
        from apps.events.models import Event
        event = Event.objects.create(makerspace=w.tenant, title="G1 public workshop", location=w.room.name,
            starts_at=w.start, ends_at=w.start + timedelta(hours=1), is_public=True, status="published")
        w.kwargs["public_token"] = event.public_token
        w.check = lambda r: equals((r.data["host"]["slug"], r.data["space"]["name"]), (w.tenant.slug, w.room.name))
        w.off["bookings"] = (200, None)
        w.policy_off = lambda key, r: equals((r.data["host"]["slug"], r.data["space"], r.data["photos"]), (w.tenant.slug, None, []))
    if w.route.standing == "public":
        w.foreign_check = w.check
