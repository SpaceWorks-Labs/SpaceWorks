"""The pricing component registry: code only, like `module_registry` (lane L15, #84).

One entry per chargeable piece of each domain. A component says its unit, whether it
takes a cap / grace / billing increment / minimum, whether automatic discounts may touch
it, which `Payment` subject it is raised under, whether staff set the amount by hand,
and which item types may override it. A later lane adds its domain here (L22 `shop`,
L6 `events.venue_fee`) and calls `pricing.quote()`; it never prices on its own.
"""

from dataclasses import dataclass

from apps.payments.models_pricing import PriceOverride, PricingDomain

T = PriceOverride.TargetType


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    unit: str
    subject_type: str | None = None
    has_cap: bool = False
    has_grace: bool = False
    has_increment: bool = False
    has_minimum: bool = False
    discountable: bool = True
    staff_set: bool = False
    targets: tuple = ()
    #: Where the space-level value lives today when it is NOT a `PricingDefaultLine`.
    legacy_default: str = ""
    #: The item field that already holds a per-item price for this component.
    legacy_item: str = ""
    #: The space rate is a prefill for new items only (events).
    prefill_only: bool = False
    read_only: bool = False


LOANS = (
    Component("rental_per_loan", "Rental per loan", "item", "loan_rental",
              targets=(T.INVENTORY_PRODUCT,)),
    Component("rental_per_day", "Rental per day", "item_day", "loan_rental", has_cap=True,
              targets=(T.INVENTORY_PRODUCT,)),
    Component("deposit", "Refundable deposit", "loan", "loan_deposit", discountable=False,
              targets=(T.INVENTORY_PRODUCT,), legacy_default="MakerspacePaymentSettings.loan_deposit_*",
              legacy_item="InventoryProduct.deposit_amount"),
    Component("late_per_day", "Late fee per day", "day", "loan_late_fee", has_cap=True, has_grace=True,
              discountable=False, targets=(T.INVENTORY_PRODUCT,),
              legacy_default="MakerspacePaymentSettings.loan_late_fee_*"),
    Component("damage", "Damage", "item", "loan_damage", discountable=False, staff_set=True,
              targets=(T.INVENTORY_PRODUCT,)),
    Component("lost", "Lost item", "item", "loan_lost", discountable=False, staff_set=True,
              targets=(T.INVENTORY_PRODUCT,)),
)
MACHINES = (
    Component("time", "Machine time per hour", "hour", "machine_service_request", has_increment=True,
              has_minimum=True, targets=(T.MACHINE,), legacy_item="MakerspaceMachineTypePricing.rate_per_unit"),
    Component("material", "Material per unit", "material_unit", "machine_service_request",
              targets=(T.MACHINE, T.CONSUMABLE_POOL), legacy_item="MakerspaceMachineTypePricing.rate_per_unit"),
    Component("per_job", "Per job", "job", "machine_service_request", targets=(T.MACHINE,),
              legacy_item="MakerspaceMachineTypePricing.flat_fee"),
)
BOOKINGS = (
    Component("per_booking", "Per booking", "booking", "booking", targets=(T.BOOKABLE_SPACE,),
              legacy_item="BookableSpace.payment_amount"),
    Component("per_hour", "Per hour", "hour", "booking", has_cap=True, has_increment=True,
              targets=(T.BOOKABLE_SPACE,)),
)
EVENTS = (
    Component("per_registration", "Per registration", "registration", "event_registration", prefill_only=True,
              legacy_item="Event.payment_amount / EventTicketType.amount"),
    # Lane L6 (#128 C-20, Q-V1): venue fees an outside organiser pays for hosting, flat and/or
    # per hour; a room may override either, and the event's own venue-fee row comes first.
    Component("venue_fee", "Venue fee", "event", "event_venue_fee", discountable=False,
              targets=(T.BOOKABLE_SPACE,), legacy_item="EventVenueFee.amount (flat)"),
    Component("venue_fee_per_hour", "Venue fee per hour", "hour", "event_venue_fee", has_increment=True,
              discountable=False, targets=(T.BOOKABLE_SPACE,), legacy_item="EventVenueFee.amount (per hour)"),
)
MEMBERSHIP = (
    Component("dues", "Membership dues", "term", "membership_term", read_only=True,
              legacy_item="MembershipPlan.amount"),
    Component("joining_fee", "Joining fee", "once", "membership_request", read_only=True,
              legacy_default="MakerspaceMembershipSettings.joining_fee"),
)

DOMAINS = {
    PricingDomain.LOANS: LOANS,
    PricingDomain.MACHINES: MACHINES,
    PricingDomain.BOOKINGS: BOOKINGS,
    PricingDomain.EVENTS: EVENTS,
    PricingDomain.MEMBERSHIP: MEMBERSHIP,
}

#: The settings-authority module that owns each domain's defaults (#101): the Space
#: Manager, or that module's manager holding its grant. Membership is read-only here.
SETTINGS_MODULES = {
    PricingDomain.LOANS: "inventory",
    PricingDomain.MACHINES: "machines",
    PricingDomain.BOOKINGS: "bookings",
    PricingDomain.EVENTS: "events",
}
#: The module key a domain needs installed (lending is core: `request_workflow`).
DOMAIN_MODULES = {
    PricingDomain.LOANS: "request_workflow",
    PricingDomain.MACHINES: "machines",
    PricingDomain.BOOKINGS: "bookings",
    PricingDomain.EVENTS: "events",
    PricingDomain.MEMBERSHIP: "membership",
}
#: Waiver component -> the loan pricing components it makes free (A14). Never the deposit.
WAIVER_COMPONENTS = {
    "rental": ("rental_per_loan", "rental_per_day"),
    "late": ("late_per_day",),
    "damage": ("damage",),
    "lost": ("lost",),
}
WAIVER_SUBJECTS = {"rental": "loan_rental", "late": "loan_late_fee", "damage": "loan_damage", "lost": "loan_lost"}


def components(domain):
    return DOMAINS.get(domain, ())


def component(domain, key):
    for entry in components(domain):
        if entry.key == key:
            return entry
    return None


def domain_known(domain):
    return domain in DOMAINS


def discountable_keys(domain):
    return frozenset(entry.key for entry in components(domain) if entry.discountable)


def editable(domain):
    """Components whose space default the pricing screen writes."""
    return tuple(entry for entry in components(domain) if not entry.read_only)
