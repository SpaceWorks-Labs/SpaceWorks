"""Shared fixtures for the L23 machine-session suites (local, untracked)."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.utils import timezone

from apps.machines.models import MachineSession
from apps.payments.models_pricing import PricingDefault, PricingDefaultLine
from apps.presence.models import PresenceSession
from tests.machines.eta_helpers import world
from tests.rbac_f6_helpers import community_member

FEATURES = {"machines.sessions", "charges.enabled", "charges.machines", "charges.pricing"}


def features(space, add=(), remove=()):
    space.enabled_features = sorted((set(space.enabled_features or []) | set(add)) - set(remove))
    space.save(update_fields=["enabled_features"])
    return space


def price(space, *, rate="120.00", increment=15, minimum=30):
    default, _ = PricingDefault.objects.update_or_create(makerspace=space, domain="machines",
                                                         defaults={"mode": "paid"})
    line, _ = PricingDefaultLine.objects.update_or_create(default=default, component="time", defaults={
        "amount": Decimal(rate), "billing_increment": increment, "minimum": minimum})
    return line


def check_in(space, membership, *, minutes_ago=10, minutes_left=120, ended_minutes_ago=None):
    now = timezone.now()
    row = PresenceSession.objects.create(
        account=membership.user, member=membership.user, makerspace=space, membership=membership,
        started_at=now - timedelta(minutes=minutes_ago), expires_at=now + timedelta(minutes=minutes_left),
        status="visiting")
    if ended_minutes_ago is not None:
        PresenceSession.objects.filter(pk=row.pk).update(ended_at=now - timedelta(minutes=ended_minutes_ago),
                                                         end_reason="user_ended")
        row.refresh_from_db()
    return row


def session_world(slug, *, billing=True, checked_in=True, **pricing):
    w = world(slug, machines=2, membership=True)
    features(w.space, FEATURES)
    if billing:
        price(w.space, **pricing)
    membership = community_member(w.space, "maker")
    if checked_in:
        check_in(w.space, membership)
    return SimpleNamespace(**vars(w), membership=membership, member=membership.user)


_SELF = object()


def open_session(w, *, member=_SELF, machine=None, minutes_ago=0, source="member_qr", **extra):
    """A live session written directly (for sweep and report tests that need past times)."""
    machine = machine or w.machines[0]
    member = w.member if member is _SELF else member
    return MachineSession.objects.create(
        makerspace=w.space, machine=machine, machine_type=machine.machine_type, member=member, source=source,
        started_at=timezone.now() - timedelta(minutes=minutes_ago), **extra)
