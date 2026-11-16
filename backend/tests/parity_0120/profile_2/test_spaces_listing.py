"""Spaces and organizations on the global profile (304b)."""
import pytest
from django.utils import timezone

from apps.makerspaces.account_profile import account_profile_for
from apps.makerspaces.account_profile_spaces import organizations_for, spaces_for
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership

from .conftest import client_for

pytestmark = pytest.mark.django_db


def test_lists_every_active_space_with_role_title(ada):
    rows = spaces_for(ada, full=True)
    assert [row["slug"] for row in rows] == ["space-a", "space-b"]
    assert rows[0]["role_title"] == "Member"


def test_excludes_revoked_hidden_archived_spaces(ada, space_a, space_b):
    MakerspaceMembership.all_tracks.filter(user=ada, makerspace=space_a).update(status="revoked")
    assert [r["slug"] for r in spaces_for(ada, full=True)] == ["space-b"]
    Makerspace.objects.filter(pk=space_b.pk).update(hidden_from_central_directory=True)
    assert spaces_for(ada, full=True) == []
    Makerspace.objects.filter(pk=space_b.pk).update(
        hidden_from_central_directory=False, archived_at=timezone.now())
    assert spaces_for(ada, full=True) == []


def test_suspended_account_profile_is_hidden(ada, grace):
    account_profile_for(ada)
    ada.access_status = ada.AccessStatus.SUSPENDED
    ada.save(update_fields=["access_status"])
    assert client_for(grace).get(f"/api/v1/profiles/by-account/{ada.pk}/").status_code == 404


def test_organizations_explicit_plus_derived_deduplicated(ada, space_a):
    org = Organization.objects.create(name="Guild", slug="guild", is_active=True, review_status="approved")
    OrganizationMakerspace.objects.create(organization=org, makerspace=space_a, relationship="owner")
    assert organizations_for(ada, full=True) == [{"slug": "guild", "name": "Guild", "source": "derived"}]
    OrganizationMembership.objects.create(organization=org, user=ada, status="active")
    assert organizations_for(ada, full=True) == [{"slug": "guild", "name": "Guild", "source": "explicit"}]


def test_manager_link_does_not_derive_membership(ada, space_a):
    org = Organization.objects.create(name="Mgr", slug="mgr", is_active=True, review_status="approved")
    OrganizationMakerspace.objects.create(organization=org, makerspace=space_a, relationship="manager")
    assert organizations_for(ada, full=True) == []
