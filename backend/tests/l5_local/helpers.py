"""Shared fixtures for the lane L5 local tests (untracked)."""

from decimal import Decimal

from apps.makerspaces.models import MakerspaceMembership
from apps.payments.models import Payment
from tests.payments.account_helpers import make_payer
from tests.return_helpers import authenticated_client, make_member, make_space


def switch(space, *keys, on=True):
    features = set(space.enabled_features or [])
    features = features | set(keys) if on else features - set(keys)
    space.enabled_features = sorted(features)
    space.save(update_fields=["enabled_features", "updated_at"])
    return space


def setup(slug, *features):
    space = make_space(slug)
    switch(space, "charges.enabled", "charges.membership", "billing.documents", *features)
    manager = make_member(f"{slug}-sm", space)
    payer = make_payer(f"{slug}-payer", space)
    return space, manager, payer


_COUNTER = {"n": 0}


def dues(space, member, amount="100.00", currency="inr", **extra):
    """One dues charge per membership: a member who already owes one gets a fresh payer."""
    if Payment.objects.filter(makerspace=space, member=member).exists():
        _COUNTER["n"] += 1
        member = make_payer(f"{space.slug}-extra-{_COUNTER['n']}", space)
    membership = MakerspaceMembership.objects.get(makerspace=space, user=member)
    return Payment.objects.create(
        makerspace=space, subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP, subject_id=membership.pk,
        member=member, amount=Decimal(amount), currency=currency, created_by=member, **extra)


def client(user):
    return authenticated_client(user)


def staff(slug, space, role):
    return make_member(f"{slug}-{role}", space, membership_role=role)


def accountless(space, manager, amount="75.00", label="Workshop fee"):
    """A loan deposit with no account behind it (an account-less borrower), raised by staff."""
    from tests.return_helpers import make_accepted_request, make_product

    request = make_accepted_request(space, make_product(space, name=f"Kit {Payment.objects.count()}"), 1)
    return Payment.objects.create(makerspace=space, subject_type=Payment.SubjectType.LOAN_DEPOSIT, subject_id=request.pk,
                                  member=None, amount=Decimal(amount), currency="inr", created_by=manager,
                                  subject_label=label)
