"""Every eligibility source, unavailable state and cross-tenant negative."""

from contextlib import nullcontext
from tests.account_split_g2_helpers import rejected_account_rows
from apps.accounts.models import User

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.events.models import EventCollaborator, EventOrganizer
from apps.events.organization_audience import (
    OrganizationAudienceRefused, candidate_ids, candidates, lock_admission_sources,
    require_organization_audience,
)
from apps.events.registration_access import require_registration_access
from apps.makerspaces.models import MakerspaceMembership
from apps.organizations.audience import eligible_accounts
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.events.organization_audience_helpers import audience_fixture, direct, local
from tests.events.ticketing_helpers import account, event_space, signup

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("source", ["direct", "owned"])
def test_all_three_organizations_admit_members_without_actions_or_venue_identity(index, source):
    venue, orgs, spaces, event, _ = audience_fixture()
    user = direct(orgs[index]) if source == "direct" else local(spaces[index])
    assert signup(event, user).status_code == 201
    assert candidate_ids(event) == {org.pk for org in orgs}
    if index != 2 or source == "direct":
        assert not MakerspaceMembership.objects.filter(user=user, makerspace=venue).exists()
    assert not rbac.can(user, rbac.Action.MANAGE_EVENTS, venue.pk)
    assert not rbac.scope_by_makerspace(user, event.__class__.objects.all()).exists() if source == "direct" else True


def test_overlap_private_profile_and_membership_module_off_still_admit():
    _, orgs, spaces, event, _ = audience_fixture()
    EventOrganizer.objects.create(event=event, organization=orgs[2])
    user = direct(orgs[0])
    OrganizationMembership.objects.create(organization=orgs[1], user=user)
    MakerspaceMembership.objects.create(makerspace=spaces[0], user=user, status="active", role="custom", assigned_role=spaces[0].roles.get(slug="member"))
    assert not orgs[0].public_profile_enabled
    assert eligible_accounts(candidate_ids(event)).filter(pk=user.pk).count() == 1
    assert signup(event, user).status_code == 201


@pytest.mark.parametrize("source,status", [("direct", "suspended"), ("owned", "suspended"), ("owned", "revoked")])
def test_nonactive_memberships_do_not_contribute_but_valid_alternative_does(source, status):
    _, orgs, spaces, event, _ = audience_fixture()
    user = direct(orgs[0], status=status) if source == "direct" else local(spaces[0])
    boundary = rejected_account_rows if source == "owned" and status == "suspended" else nullcontext
    with boundary():
        if source == "owned":
            MakerspaceMembership.objects.filter(user=user).update(status=status)
        with pytest.raises(OrganizationAudienceRefused):
            require_organization_audience(event, user)
        OrganizationMembership.objects.create(organization=orgs[1], user=user, status="active")
        if boundary is nullcontext:
            assert signup(event, user).status_code == 201
        else:
            # The DB refuses a suspended owned membership at flush, so this state only
            # exists inside that doomed transaction, and registration (a write command)
            # refuses to run inside a caller's transaction. Assert the admission readers.
            require_organization_audience(event, user)
            assert eligible_accounts(candidate_ids(event)).filter(pk=user.pk).count() == 1


@pytest.mark.parametrize("kind", ["unrelated_org", "unrelated_space", "manager", "affiliate", "collaborator", "missing"])
def test_unrelated_or_nonowner_sources_never_widen_audience(kind):
    _, orgs, _, event, _ = audience_fixture()
    space = event_space("unrelated")
    if kind in ("manager", "affiliate"):
        OrganizationMakerspace.objects.create(organization=orgs[0], makerspace=space, relationship=kind)
    if kind == "collaborator":
        EventCollaborator.objects.create(event=event, makerspace=space, status="accepted")
    user = direct(Organization.objects.create(name="Other", slug="other")) if kind == "unrelated_org" else (
        account() if kind == "missing" else local(space))
    assert signup(event, user).status_code == 403
    assert not event.registrations.exists()


@pytest.mark.parametrize("field,value", [("is_active", False), ("access_status", "restricted"),
                                        ("access_status", "suspended"), ("is_tenant_dump_stub", True)])
def test_fresh_account_state_is_required_even_with_stale_identity(field, value):
    _, orgs, _, event, _ = audience_fixture()
    user = direct(orgs[0])
    user.__class__.objects.filter(pk=user.pk).update(**{field: value})
    with pytest.raises(OrganizationAudienceRefused):
        require_organization_audience(event, user)


@pytest.mark.parametrize("target", ["source", "venue"])
@pytest.mark.parametrize("state", ["archived", "inactive"])
def test_unavailable_spaces_never_contribute(target, state, monkeypatch):
    venue, _, spaces, event, _ = audience_fixture()
    user = local(spaces[0])
    space = venue if target == "venue" else spaces[0]
    changes = {"archived_at": timezone.now()} if state == "archived" else {"lifecycle_state": "migrated_out"}
    space.__class__.objects.filter(pk=space.pk).update(**changes)
    with pytest.raises(OrganizationAudienceRefused):
        require_organization_audience(event, user)


def test_inactive_org_and_live_organizer_removal_owner_relink():
    venue, orgs, _, event, _ = audience_fixture()
    user = direct(orgs[0])
    orgs[0].is_active = False; orgs[0].save(update_fields=["is_active"])
    assert orgs[0].pk not in set(candidates(event).values_list("pk", flat=True))
    with pytest.raises(OrganizationAudienceRefused):
        require_organization_audience(event, user)
    user = direct(orgs[2], "owner-member")
    OrganizationMakerspace.objects.filter(makerspace=venue, relationship="owner").delete()
    with pytest.raises(OrganizationAudienceRefused):
        require_organization_audience(event, user)
    user = direct(orgs[1], "organizer-member")
    EventOrganizer.objects.filter(event=event, organization=orgs[1]).delete()
    with pytest.raises(OrganizationAudienceRefused):
        require_organization_audience(event, user)
    EventOrganizer.objects.filter(event=event).delete()
    assert not candidate_ids(event)


@pytest.mark.parametrize("staff,collaborative", [(False, False), (True, False), (False, True), (True, True)])
def test_service_flags_and_superadmin_cannot_bypass(staff, collaborative):
    _, _, _, event, _ = audience_fixture()
    user = User.objects.create_superuser(username="audience-root", password=None)
    for member in (None, user):
        with pytest.raises(OrganizationAudienceRefused):
            require_registration_access(event, member, staff=staff, collaborative=collaborative)
    assert APIClient().post(f"/api/v1/public/{event.makerspace.slug}/events/{event.public_token}/register/", {}, format="json").status_code == 401
