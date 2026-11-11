"""Candidate lists and submitted IDs agree on member-only community ownership."""
from datetime import timedelta

import pytest
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.bookings.models import BookableSpace
from apps.events.speaker_identity import assign_speaker, candidate_accounts
from apps.hardware_requests.direct_loan_views import _borrower_for_makerspace
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.organizations.audience import eligible_accounts
from apps.organizations.models import Organization, OrganizationMakerspace
from apps.presence.views_staff import scoped_account
from tests.account_split.p1_helpers import staff
from tests.events.test_staff_registration_p13 import make_event, member
from .helpers import bearer_client

pytestmark = pytest.mark.django_db


@pytest.fixture
def roster():
    space = Makerspace.objects.create(name="Picker lab", slug="s4b-picker")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"membership", "events", "bookings", "presence"})
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.self_checkout"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    manager, _ = staff(space, "s4b-picker-manager", role="space_manager")
    operator, _ = staff(space, "s4b-picker-operator", email="same@example.test")
    community = member(space, username="s4b-picker-member")
    # Matching contact details never make the staff identity a community candidate.
    community.email = operator.email
    community.save(update_fields=["email"])
    platform = User.objects.create_superuser("s4b-picker-platform")
    foreign = member(Makerspace.objects.create(name="Other", slug="s4b-other"),
                     username="s4b-outsider", phone="+15550100101")
    return space, manager, operator, community, platform, foreign


def test_loan_picker_and_borrower_resolution_exclude_staff_platform_and_other_tenants(roster):
    space, manager, operator, community, platform, foreign = roster
    response = bearer_client(manager).get(reverse("hardware_requests:direct-loan-members", args=[space.pk]))
    assert response.status_code == 200, response.data
    assert {row["user_id"] for row in response.data["results"]} == {community.pk}
    assert _borrower_for_makerspace(space, community.pk).pk == community.pk
    for account in (manager, operator, platform, foreign):
        with pytest.raises(PermissionDenied):
            _borrower_for_makerspace(space, account.pk)


def test_event_candidates_and_registration_resolution_are_member_only(roster):
    space, manager, operator, community, platform, foreign = roster
    event = make_event(space)
    api = bearer_client(manager)
    response = api.get(reverse("admin-event-eligible-members", args=[event.pk]))
    assert response.status_code == 200, response.data
    assert {row["member_id"] for row in response.data} == {community.pk}
    for account in (operator, platform, foreign):
        response = api.post(f"/api/v1/admin/events/{event.pk}/registrations/",
                            {"member_id": account.pk}, format="json")
        assert response.status_code == 404, response.data
    response = api.post(f"/api/v1/admin/events/{event.pk}/registrations/",
                        {"member_id": community.pk}, format="json")
    assert response.status_code == 201, response.data


def test_booking_candidates_and_id_resolution_are_member_only(roster):
    space, manager, operator, community, platform, foreign = roster
    room = BookableSpace.objects.create(makerspace=space, name="Room")
    api = bearer_client(manager)
    response = api.get(reverse("admin-space-booking-eligible-members", args=[room.pk]))
    assert response.status_code == 200, response.data
    assert {row["member_id"] for row in response.data["results"]} == {community.pk}
    starts = timezone.now() + timedelta(days=1)
    for account in (operator, platform, foreign):
        response = api.post(reverse("admin-space-booking-list", args=[room.pk]), {
            "member_id": account.pk, "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=1)).isoformat(),
        }, format="json")
        assert response.status_code == 404, response.data


def test_payment_presence_and_member_card_rosters_never_offer_staff(roster):
    space, manager, operator, community, platform, foreign = roster
    api = bearer_client(manager, recent=True)
    response = api.get("/api/v1/admin/memberships", {"makerspace_id": space.pk, "status": "active"})
    assert response.status_code == 200, response.data
    assert {row["user"]["id"] for row in response.data["results"]} == {community.pk}
    legacy = api.get(f"/api/v1/admin/makerspaces/{space.pk}/memberships")
    assert legacy.status_code == 200, legacy.data
    assert {row["user"]["id"] for row in legacy.data} == {community.pk}
    search = api.get("/api/v1/admin/search", {"makerspace_id": space.pk, "q": "s4b-picker"})
    assert search.status_code == 200, search.data
    labels = [row["label"] for row in search.data["results"] if row["entity"] == "members"]
    assert labels == [community.username]
    assert scoped_account(space, community.pk).pk == community.pk
    for account in (operator, platform, foreign):
        with pytest.raises(Http404):
            scoped_account(space, account.pk)
    # The staff lifecycle roster remains a separate, usable staff picker.
    response = api.get(f"/api/v1/admin/makerspaces/{space.pk}/staff-accounts/")
    assert response.status_code == 200, response.data
    assert {row["id"] for row in response.data["results"]} == {manager.pk, operator.pk}


def test_organization_audience_and_speaker_candidates_use_community_accounts(roster):
    space, manager, operator, community, platform, foreign = roster
    organization = Organization.objects.create(name="Audience", slug="s4b-audience")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=space, relationship="owner")
    assert set(eligible_accounts([organization.pk]).values_list("pk", flat=True)) == {community.pk}
    event = make_event(space)
    assert set(candidate_accounts(event, "s4b-picker").values_list("pk", flat=True)) == {community.pk}
    for account in (operator, platform, foreign):
        with pytest.raises(ValidationError):
            assign_speaker(event, actor=manager, user=account)


def test_organization_admin_autocomplete_and_form_refuse_staff(roster):
    from django.contrib import admin
    from django.test import RequestFactory
    from apps.organizations.admin_memberships import OrganizationMembershipForm

    _, _, operator, community, platform, _ = roster
    request = RequestFactory().get("/control/autocomplete/", {
        "app_label": "organizations", "model_name": "organizationmembership", "field_name": "user",
    })
    request.user = platform
    candidates, _ = admin.site._registry[User].get_search_results(request, User.objects.all(), "")
    assert candidates.filter(pk=community.pk).exists()
    assert not candidates.filter(pk__in=[operator.pk, platform.pk]).exists()
    choices = OrganizationMembershipForm().fields["user"].queryset
    assert choices.filter(pk=community.pk).exists() and not choices.filter(pk=operator.pk).exists()


def test_training_candidates_and_grants_use_member_accounts(roster):
    from apps.machines.certification_grants import issue_grant
    from tests.machines.certification_helpers import _certification, _machine_type

    space, manager, operator, community, _, _ = roster
    space.enabled_features = sorted(set(space.enabled_features) | {"machines.certifications"})
    space.save(update_fields=["enabled_features"])
    training = _certification(space, _machine_type(space))
    response = bearer_client(manager).get(reverse("admin-certification-members", args=[training.pk]))
    assert response.status_code == 200, response.data
    membership = MakerspaceMembership.objects.get(user=community)
    assert {row["id"] for row in response.data["results"]} == {membership.pk}
    with pytest.raises(PermissionDenied):
        issue_grant(training, MakerspaceMembership.objects.get(user=operator), actor=manager)


def test_machine_intake_refuses_nonmember_ids_before_workflow(roster):
    space, manager, operator, _, platform, foreign = roster
    api = bearer_client(manager)
    for account in (operator, platform, foreign):
        response = api.post(f"/api/v1/admin/makerspaces/{space.pk}/machine-service/requests", {
            "requester_id": account.pk, "machine_id": 1, "title": "Member job",
        }, format="json")
        assert response.status_code == 404, response.data
