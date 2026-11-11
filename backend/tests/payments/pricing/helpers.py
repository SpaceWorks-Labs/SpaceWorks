"""Shared fixtures for the lane L15 pricing tests (local, untracked)."""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.payments.models import MakerspacePaymentSettings, PricingDefault, PricingDefaultLine
from tests.return_helpers import authenticated_client, make_member, make_space

D = Decimal


def switch(space, *keys, on=True):
    features = set(space.enabled_features or [])
    features = features | set(keys) if on else features - set(keys)
    space.enabled_features = sorted(features)
    space.save(update_fields=["enabled_features", "updated_at"])
    return space


def pricing_space(slug, *features, **settings):
    """A space with charge tracking, price lists and loans on; settings go on the payment row."""
    space = make_space(slug)
    switch(space, "charges.enabled", "charges.loans", "charges.bookings", "charges.events", "charges.machines",
           "charges.membership", "charges.pricing", "loans.enabled", "loans.fee_waivers", *features)
    row, _ = MakerspacePaymentSettings.objects.get_or_create(makerspace=space)
    for name, value in settings.items():
        setattr(row, name, value)
    row.save()
    manager = make_member(f"{slug}-sm", space)
    return space, manager


def rate(space, domain, mode="paid", **lines):
    """`rate(space, "loans", rental_per_day=("2.00", {"cap": "5.00"}))`."""
    row, _ = PricingDefault.objects.update_or_create(makerspace=space, domain=domain, defaults={"mode": mode})
    for component, value in lines.items():
        amount, extra = (value, {}) if not isinstance(value, tuple) else value
        PricingDefaultLine.objects.update_or_create(default=row, component=component,
                                                    defaults={"amount": D(amount), **extra})
    return row


def member(space, username=None):
    user = make_member(username or f"m-{uuid.uuid4().hex[:8]}", space, membership_role="member", role="requester")
    user.phone = "+9198" + str(uuid.uuid4().int)[:8]
    user.save(update_fields=["phone"])
    return user


def plan(space, name="Pro", amount="10.00"):
    return MembershipPlan.objects.create(makerspace=space, name=name, interval="monthly", amount=D(amount),
                                         currency="usd")


def put_on_plan(space, user, the_plan):
    membership = MakerspaceMembership.objects.get(makerspace=space, user=user)
    now = timezone.now()
    return MembershipTerm.objects.create(membership=membership, plan=the_plan, starts_at=now - timedelta(days=1),
                                         ends_at=now + timedelta(days=29))


def client(user):
    return authenticated_client(user)
