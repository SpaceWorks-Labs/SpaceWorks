"""Organization authority belongs to member browser accounts."""

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from apps.organizations import governance
from apps.organizations.access import lock_governance_membership
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.services_console import OrganizationConflict
from apps.organizations.services_governance import self_departure, update_membership
from apps.organizations.services_self_service import creation_policy
from tests.fixed_roles.helpers import staff_account

pytestmark = pytest.mark.django_db


def governed():
    org = Organization.objects.create(name="Members", slug="recon-governance")
    user = User.objects.create_user(username="recon-governor")
    row = OrganizationMembership.objects.create(
        organization=org, user=user, governance_actions=sorted(governance.GOVERNANCE_ACTIONS),
    )
    return org, user, row


def test_native_governor_has_no_delegated_authority_but_keeps_internal_departure_rules():
    org, user, row = governed()
    user.native_device_session = True
    assert governance.actions_for(user, org) == set()
    assert not governance.has_any_governance(user)
    with pytest.raises(PermissionDenied):
        update_membership(org, row.pk, actor=user, governance_actions=[])
    # Native member account deletion must still preserve the last governor.
    with pytest.raises(OrganizationConflict):
        self_departure(org, user=user)


@pytest.mark.skip(reason="U-A1: a staff-role holder is a person, so an organization membership on that person is live authority, not stale")
def test_staff_cannot_use_a_stale_organization_membership():
    org, _member, _row = governed()
    space = Makerspace.objects.create(name="Staff", slug="recon-staff")
    staff = staff_account(space, "recon-staff")
    stale = OrganizationMembership.objects.create(
        organization=org, user=staff, governance_actions=sorted(governance.GOVERNANCE_ACTIONS),
    )
    assert governance.actions_for_membership(stale) == set()
    assert governance.actions_for(staff, org) == set()
    with pytest.raises(PermissionDenied):
        lock_governance_membership(staff, org, governance.MANAGE_ORGANIZATION_MEMBERS)
    with pytest.raises(PermissionDenied):
        self_departure(org, user=staff)


def test_inactive_successor_does_not_allow_last_live_governor_departure():
    org, user, _row = governed()
    successor = User.objects.create_user(username="recon-inactive-successor", is_active=False)
    OrganizationMembership.objects.create(
        organization=org, user=successor, governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS],
    )
    with pytest.raises(OrganizationConflict):
        self_departure(org, user=user)


def test_native_self_creation_cannot_mint_organization_governance(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    _org, user, _row = governed()
    user.email = "recon@example.test"
    user.email_verified_at = timezone.now()
    assert creation_policy(user)["eligible"]
    user.native_device_session = True
    assert not creation_policy(user)["eligible"]


@pytest.mark.django_db(transaction=True)
def test_simultaneous_governor_departures_preserve_one_live_governor():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections, connections

    org, first, _row = governed()
    second = User.objects.create_user(username="recon-second-governor")
    OrganizationMembership.objects.create(
        organization=org, user=second, governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS],
    )
    barrier = Barrier(2)

    def depart(user_id):
        close_old_connections()
        try:
            user = User.objects.get(pk=user_id)
            barrier.wait(timeout=10)
            try:
                self_departure(org, user=user)
                return "departed"
            except OrganizationConflict:
                return "refused"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(depart, (first.pk, second.pk)))
    assert sorted(outcomes) == ["departed", "refused"]
    assert OrganizationMembership.objects.filter(organization=org, status="active").count() == 1
