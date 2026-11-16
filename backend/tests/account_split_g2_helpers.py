"""Account-kind-aware builders and a rollback boundary for corruption tests."""
from contextlib import contextmanager

import pytest
from django.db import IntegrityError, transaction

from tests.account_split.p1_helpers import flush_constraints, staff
from tests.fixed_roles.helpers import assign_builtin_roles, roles_for_actions


def staff_for_actions(space, username, actions, *, machine_types=()):
    roles = roles_for_actions(space, actions)
    if roles[0].slug == "member":
        from apps.accounts.models import User
        user = User.objects.create_user(username, email=f"{username}@e.com", access_status="active")
        return user, assign_builtin_roles(user, space, "member")
    with transaction.atomic():
        user, membership = staff(space, username, roles[0].slug,
                                 email=f"{username}@e.com", access_status="active")
        assign_builtin_roles(user, space, *(role.slug for role in roles), machine_types=machine_types)
    return user, membership


@contextmanager
def rejected_account_rows():
    """Keep reader assertions reachable, then require the deferred DB guard to refuse."""
    with pytest.raises(IntegrityError), transaction.atomic():
        yield
        flush_constraints()


def grant_organization_action(space, user, action):
    from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
    organization = Organization.objects.create(name="Report auditors", slug=f"audit-{space.pk}-{user.pk}")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=space, relationship="owner")
    return OrganizationMembership.objects.create(organization=organization, user=user, granted_actions=[action])
