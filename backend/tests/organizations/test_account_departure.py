import pytest

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.organizations import governance
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.services_console import OrganizationConflict
from apps.organizations.services_governance import self_departure

pytestmark = pytest.mark.django_db


def membership(user, *, actions=()):
    org = Organization.objects.create(name="Departure", slug="departure")
    return OrganizationMembership.objects.create(
        organization=org, user=user, governance_actions=list(actions),
    )


def test_member_without_governance_authority_can_depart():
    user = User.objects.create_user(username="departing")
    target = membership(user)
    result = self_departure(target.organization, user=user)
    target.refresh_from_db()
    assert result.pk == target.pk
    assert target.status == OrganizationMembership.Status.SUSPENDED
    entry = AuditLog.objects.get(action="organization.member_departed")
    assert entry.actor_id == user.pk
    assert entry.target_id == str(target.pk)
    assert entry.meta == {"status": "suspended"}


def test_last_governor_cannot_depart():
    user = User.objects.create_user(username="sole-governor")
    target = membership(user, actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    with pytest.raises(OrganizationConflict):
        self_departure(target.organization, user=user)
    target.refresh_from_db()
    assert target.status == OrganizationMembership.Status.ACTIVE
    assert not AuditLog.objects.filter(action="organization.member_departed").exists()


def test_governor_can_depart_when_successor_remains():
    user = User.objects.create_user(username="outgoing")
    target = membership(user, actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    successor = OrganizationMembership.objects.create(
        organization=target.organization,
        user=User.objects.create_user(username="successor"),
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS],
    )
    self_departure(target.organization, user=user)
    target.refresh_from_db()
    successor.refresh_from_db()
    assert target.status == OrganizationMembership.Status.SUSPENDED
    assert successor.status == OrganizationMembership.Status.ACTIVE


def test_departure_is_owned_and_idempotent():
    user = User.objects.create_user(username="departing")
    target = membership(user)
    outsider = User.objects.create_user(username="outsider")
    assert self_departure(target.organization, user=outsider) is None
    target.refresh_from_db()
    assert target.status == OrganizationMembership.Status.ACTIVE
    self_departure(target.organization, user=user)
    self_departure(target.organization, user=user)
    assert AuditLog.objects.filter(action="organization.member_departed").count() == 1


def test_departure_rolls_back_with_account_deletion_transaction():
    from django.db import transaction

    user = User.objects.create_user(username="rollback")
    target = membership(user)
    with pytest.raises(ValueError), transaction.atomic():
        self_departure(target.organization, user=user)
        raise ValueError("abort deletion")
    target.refresh_from_db()
    assert target.status == OrganizationMembership.Status.ACTIVE
    assert not AuditLog.objects.filter(action="organization.member_departed").exists()
