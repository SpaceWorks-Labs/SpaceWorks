"""0.12.0 audit row 9: `has_organizations` on the auth payload.

The staff console shows its cross-venue Organizations group (organizations, organized
events, organization analytics) only when this flag is true, so it must say exactly what
the Organizations list (`organizations.access.visible_organizations`) would show.
"""

import pytest

from apps.accounts.models import User
from apps.accounts.serializers import user_payload
from apps.organizations.models import OrganizationMembership
from tests.organizations.test_org_authority import grant, make_organization, make_user


pytestmark = pytest.mark.django_db


def test_person_without_any_organization_has_none():
    user = make_user("payload-no-org")

    assert user_payload(user)["has_organizations"] is False


def test_active_membership_without_granted_actions_counts():
    # Governance-only membership: no makerspace actions, still an organization relationship.
    user = make_user("payload-org-governor")
    grant(make_organization("payload-org-governed"), user, [],
          governance_actions=["manage_organization_profile"])

    assert user_payload(user)["has_organizations"] is True


def test_suspended_membership_does_not_count():
    user = make_user("payload-org-suspended")
    grant(make_organization("payload-org-suspended-org"), user, ["manage_events"],
          status=OrganizationMembership.Status.SUSPENDED)

    assert user_payload(user)["has_organizations"] is False


def test_inactive_organization_does_not_count():
    user = make_user("payload-org-inactive")
    grant(make_organization("payload-org-inactive-org", is_active=False), user, ["manage_events"])

    assert user_payload(user)["has_organizations"] is False


def test_superadmin_is_never_flagged():
    # The platform account governs organizations from the platform pages, not this group.
    root = make_user("payload-org-root", role=User.Role.SUPERADMIN, is_superuser=True)
    make_organization("payload-org-root-org")

    assert user_payload(root)["has_organizations"] is False


def test_me_endpoint_carries_the_flag():
    from rest_framework.test import APIClient

    user = make_user("payload-org-me")
    grant(make_organization("payload-org-me-org"), user, ["manage_events"])
    client = APIClient()
    client.force_authenticate(user)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["has_organizations"] is True
