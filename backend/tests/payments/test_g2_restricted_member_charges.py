"""Decision 260 G-1: a restricted or suspended account can see and pay its own charges; revoked cannot."""

import pytest

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from apps.payments.member_access import member_may_see_own_charges, member_payment_actor
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("status", [User.AccessStatus.RESTRICTED, User.AccessStatus.SUSPENDED])
def test_restricted_or_suspended_member_still_reaches_own_charges(status):
    space = make_space(f"g1-{status}")
    member = make_member(f"g1-{status}", space, membership_role="member", role=User.Role.REQUESTER)
    User.objects.filter(pk=member.pk).update(access_status=status)
    member.refresh_from_db()
    assert member_payment_actor(member, space.pk) is not None
    assert member_may_see_own_charges(member, space.pk)


def test_revoked_membership_is_still_refused():
    space = make_space("g1-revoked")
    member = make_member("g1-revoked", space, membership_role="member", role=User.Role.REQUESTER)
    MakerspaceMembership.objects.filter(user=member, makerspace=space).update(status="revoked")
    assert member_payment_actor(member, space.pk) is None
    assert not member_may_see_own_charges(member, space.pk)


def test_inactive_account_is_refused():
    space = make_space("g1-inactive")
    member = make_member("g1-inactive", space, membership_role="member", role=User.Role.REQUESTER)
    User.objects.filter(pk=member.pk).update(is_active=False)
    member.refresh_from_db()
    assert not member_may_see_own_charges(member, space.pk)
