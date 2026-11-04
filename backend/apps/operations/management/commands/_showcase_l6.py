"""Tinkerspace paid ticketing v2 (release 2 L6, #134 walkthrough), through the real services.

Turns on the ticket-order switches and seeds one ticketed build night: an early-bird tier
that hands over to a regular tier, a pay-what-you-want supporter ticket, a hidden crew
ticket behind an access code, a T-shirt add-on with sizes, a booking fee, transfers on,
its own refund policy, and a venue fee charged to an outside organiser on publish.
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.events import addons, cancellation_policy, promos, services, venue_fees
from apps.events.models import EventSalesSettings
from apps.events.ticketing import create_ticket
from apps.makerspaces.models import Makerspace

FEATURES = ("events.ticket_types", "events.promo_codes", "events.orders", "events.seat_holds", "events.addons",
            "events.transfers", "events.desk_collect", "events.refund_override", "events.venue_fees",
            "charges.enabled", "charges.events")
CREW_CODE = "TINKER-CREW-2026"


def seed_ticketing(space, manager, organiser):
    space.enabled_features = sorted(set(space.enabled_features or []) | set(FEATURES))
    Makerspace.objects.filter(pk=space.pk).update(enabled_features=space.enabled_features)
    starts = (timezone.now() + timedelta(days=16)).replace(hour=18, minute=0, second=0, microsecond=0)
    event = services.create_event(
        makerspace=space, actor=manager, title="Build night: robot arena", description="Bring a bot, or build one.",
        starts_at=starts, ends_at=starts + timedelta(hours=4), location="Main workshop", capacity=40,
        is_public=True, listing="listed", registration_audience="accounts")
    create_ticket(event, actor=manager, name="Early bird", amount=Decimal("8.00"), capacity=10,
                  tier_group="general", tier_rank=0)
    create_ticket(event, actor=manager, name="Regular", amount=Decimal("12.00"), tier_group="general", tier_rank=1)
    create_ticket(event, actor=manager, name="Supporter", amount=Decimal("20.00"), pricing_mode="pwyw",
                  min_amount=Decimal("5.00"))
    crew = create_ticket(event, actor=manager, name="Crew", amount=Decimal("0"), is_hidden=True)
    promos.create_promo(event, actor=manager, code=CREW_CODE, kind="access", ticket_type_id=crew.pk, max_uses=10)
    addons.create_addon(event, actor=manager, name="Arena T-shirt", kind="merch", amount=Decimal("10.00"),
                        variants=[{"label": "M", "stock": 15}, {"label": "L", "stock": 15}])
    EventSalesSettings.objects.update_or_create(event=event, defaults={
        "makerspace": space, "booking_fee_fixed": Decimal("0.50"), "booking_fee_bps": 200, "transfers_allowed": True,
        "type_changes_allowed": True, "transfer_cutoff_hours": 24})
    cancellation_policy.set_override(event, actor=manager, enabled=True, values={
        "full_before_minutes": 2880, "partial_before_minutes": 720, "partial_percent": 50,
        "cancellation_fee": Decimal("0")}, policy_text="Full refund up to two days before; half up to 12 hours before.")
    venue_fees.configure(event, actor=manager, payer=organiser, mode="custom", basis="per_hour", amount=Decimal("15.00"))
    return services.publish(event, actor=manager)
