"""Actors and tenant-local records for the finer RBAC endpoint matrix."""
from tests.account_split.sweep_helpers import (
    configured_membership as _configured_membership,
    make_role_account as _make_role_account,
)
from django.utils import timezone
from django.db import transaction

from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from apps.payments.models import Payment
from tests.return_helpers import make_user


@transaction.atomic
def custom_actor(space, actions, name="delegate"):
    user = make_user(f"{space.slug}-{name}", access_status="active",
                     account_kind="staff" if actions else "member",
                     staff_makerspace=space if actions else None)
    from tests.fixed_roles.helpers import membership_for_actions

    membership_for_actions(user, space, actions)
    return user


def community_member(space, name="member"):
    user = _make_role_account(
        space,
        role_slug=(MakerspaceRole.objects.get(makerspace=space, slug="member")).slug,
        username=f"{space.slug}-{name}",
        access_status="active",
        email=str(f"{space.slug}-{name}") + "@e.com",
    )
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return _configured_membership(user=user, makerspace=space)


def charge(space, membership, status="pending"):
    return Payment.objects.create(
        makerspace=space, member=membership.user, created_by=membership.user,
        subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
        subject_id=membership.pk, amount="12.00", currency="usd", status=status,
    )
