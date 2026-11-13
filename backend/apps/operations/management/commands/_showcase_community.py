"""Money, rooms, notices and the public page for the showcase space.

Dues are raised by the membership services when each member is approved (the space
charges 25.00 and has no live gateway, so every charge is stamped `unclaimed`); some
are then settled offline with a ManualSettlement receipt through `reconcile_payments`.
Bookings, the member broadcast, the staff feed and the public page all go through
their own services.
"""
import uuid
from datetime import timedelta

from django.utils import timezone

from apps.bookings import services as bookings
from apps.bookings.models import BookableSpace
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.public_profile_handles import name_available
from apps.makerspaces.setup_settings import save_plan
from apps.notifications.broadcasts import send_broadcast
from apps.notifications.emit import emit_notification
from apps.payments.models import Payment
from apps.payments.reconciliation import reconcile_payments

from . import _showcase_data as data

ABOUT = (
    "Tinkerspace is a community workshop run by its members. Borrow tools from the "
    "tool library, send a print to the farm, book a bench, or drop in on a "
    "Thursday repair night.\n\nEverything here is showcase data for a demo space."
)


def membership_plan(space, manager):
    return save_plan(manager, space, {"name": "Monthly maker", "interval": "monthly",
                                      "amount": "25.00", "currency": "usd"})


def settle_some_dues(space, manager, members):
    settled = ("asha_menon", "ravi_kumar", "lena_ortiz", "kofi_mensah", "priya_nair", "noor_rahman")
    methods = ("cash", "upi", "bank_transfer", "card_machine", "cash", "cheque")
    pending = Payment.objects.filter(makerspace=space, status=Payment.Status.PENDING,
                                     member__in=[members[name] for name in settled]).order_by("pk")
    for index, payment in enumerate(pending):
        reconcile_payments(
            actor=manager, makerspace_id=space.pk, payment_ids=[payment.pk],
            target_status=Payment.Status.PAID_OFFLINE,
            settlement={"method": methods[index % len(methods)],
                        "reference": f"TS-RCPT-{index + 1:04d}", "received_at": timezone.now()},
        )


def seed_bookings(space, manager, members):
    bench = bookings.create_space(
        makerspace=space, actor=manager, name="Electronics Bench", kind=BookableSpace.Kind.BENCH,
        description="Soldering bench with fume extraction and a bench power supply.",
        capacity=2, location="Electronics bay", is_public=True, show_public_availability=True,
    )
    room = bookings.create_space(
        makerspace=space, actor=manager, name="Workshop Classroom", kind=BookableSpace.Kind.MEETING,
        description="Seats twelve; projector and whiteboard. Staff approve each booking.",
        capacity=12, location="First floor", is_public=True, show_public_availability=True,
        approval_mode=BookableSpace.ApprovalMode.APPROVE,
    )
    base = (timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    for offset, username in ((0, "asha_menon"), (3, "kofi_mensah"), (26, "aiko_tanaka")):
        start = base + timedelta(hours=offset)
        bookings.create_booking(bench, starts_at=start, ends_at=start + timedelta(hours=2),
                                member=members[username], note="Showcase booking")
    confirmed = bookings.create_booking(room, starts_at=base + timedelta(days=2),
                                        ends_at=base + timedelta(days=2, hours=3),
                                        member=members["noor_rahman"], note="Intro to CAD class")
    bookings.approve_booking(confirmed, actor=manager)
    bookings.create_booking(room, starts_at=base + timedelta(days=4),
                            ends_at=base + timedelta(days=4, hours=2),
                            member=members["diego_ramos"], note="Van build meetup")
    return bench, room


def seed_notices(space, manager):
    emit_notification(space, title="PETG filament is running low", level="warning",
                      event="stock.low", body="Reorder draft raised for PETG Filament 1 kg.")
    emit_notification(space, title="ESP32 loan is overdue", level="warning",
                      event="loan.overdue", body="Mei Lin Chua's loan was due three days ago.")
    emit_notification(space, title="Laser cutter maintenance is due", level="info",
                      event="maintenance.due", body="Optics clean and alignment check.")
    send_broadcast(space, actor=manager, title="Repair night this Thursday",
                   body="Bring something broken. Soldering stations and tea from 6 pm.")


def publish_public_page(space, manager):
    state = pages.read_editor("makerspace", space.pk, actor=manager)
    handle = next(name for name in (data.SLUG, f"{data.SLUG}.space", f"{data.SLUG}.makers",
                                    f"{data.SLUG}-{uuid.uuid4().hex[:6]}") if name_available(name))
    state = pages.change_handle("makerspace", space.pk, actor=manager,
                                version=state["version"], handle=handle)
    document = dict(state["document"])
    document["sections"] = [
        _section("about", {"title": "About Tinkerspace", "markdown": ABOUT}),
        _section("stats", {"title": "Tinkerspace in numbers", "show_public_inventory_units": True,
                           "show_published_event_count": True, "publish_public_member_count": True}),
        _section("upcoming_events", {"title": "Coming up"}),
        _section("location", {"title": "Find us", "enabled_publicly": True,
                              "source": "makerspace_public"}),
        *document["sections"],
    ]
    state = pages.save("makerspace", space.pk, actor=manager, version=state["version"],
                       document=document)
    return pages.publish("makerspace", space.pk, actor=manager, version=state["version"],
                         draft_revision_id=state["draft_revision_id"])


def _section(kind, payload):
    return {"id": str(uuid.uuid4()), "type": kind, "enabled": True, "payload": payload}
