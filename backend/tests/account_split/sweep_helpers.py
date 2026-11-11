"""Explicit account contexts for the legacy workflow fixture builders."""

from django.db import transaction

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.account_factories import make_membership, make_staff


def create_test_user(*args, **fields):
    """Honor explicit platform intent without ever promoting a saved account.

    One account per person (U-A1): legacy staff hints are dropped; the caller's role grant
    makes the person staff."""
    if fields.get("account_kind") == "staff":
        fields.pop("account_kind")
    fields.pop("staff_makerspace", None)
    if fields.get("is_superuser") or fields.get("role") == User.Role.SUPERADMIN:
        fields["role"] = User.Role.SUPERADMIN
        return User.objects.create_superuser(*args, **fields)
    return User.objects.create_user(*args, **fields)


def role_slug(legacy):
    return {"custom": "member", "print_manager": "machine_manager"}.get(legacy, legacy)


@transaction.atomic
def make_role_account(makerspace, *, role_slug, username, **fields):
    """Mixed-role fixture builders choose the account kind before inserting it."""
    fields.pop("account_kind", None)  # one account per person: the role decides
    fields.pop("staff_makerspace", None)
    if role_slug == "member":
        user = User.objects.create_user(username=username, **fields)
        make_membership(user, makerspace)
        return user
    return make_staff(makerspace, username=username, role_slug=role_slug, **fields)


def configured_membership(*, user, makerspace, **fields):
    """Apply lifecycle/notification fixture fields to the factory's existing row."""
    membership = (MakerspaceMembership.objects.filter(user=user, makerspace=makerspace).first()
                  or MakerspaceMembership.staff_tracks.get(user=user, makerspace=makerspace))
    for name, value in fields.items():
        setattr(membership, name, value)
    if fields:
        membership.save(update_fields=list(fields))
    return membership
