"""Organization directory, organizers/partners at creation, audience organizations."""
from tests.events.manual_grant_fixture import create_manual_grant

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.events import event_authority
from apps.events.audience_models import EventAudienceOrganization
from apps.events.models import Event, EventCollaborator, EventOrganizer, EventStaffGrant
from apps.events.organization_audience import AUDIENCE, FEATURE, candidate_ids, require_organization_audience
from apps.organizations.models import Organization, OrganizationMembership
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db

DIRECTORY = "admin-organization-directory"
PARTNERS = "admin-event-partner-makerspaces"


def org(slug, **values):
    return Organization.objects.create(name=slug.title(), slug=slug, **values)


def member(organization, user, actions=()):
    return OrganizationMembership.objects.create(organization=organization, user=user, granted_actions=list(actions))


def audience_url(event):
    return reverse("admin-event-audience-organizations", kwargs={"pk": event.pk})


def create_url(space):
    return reverse("admin-event-list-create", kwargs={"makerspace_id": space.pk})


def payload(**extra):
    starts = timezone.now() + timedelta(days=2)
    return {"title": "Partnered", "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=2)).isoformat(), **extra}


def slugs(response):
    return [row["slug"] for row in response.data["results"]]


# -- Organization directory -------------------------------------------------------------

def test_directory_lists_only_discoverable_or_own_active_organizations():
    space = event_space("dir-host")
    staff = make_staff(space)
    org("listed", is_discoverable=True)
    org("unlisted")
    org("gone", is_discoverable=True, is_active=False)
    mine = org("mine")
    member(mine, staff)

    response = client_for(staff).get(reverse(DIRECTORY))
    assert response.status_code == 200
    assert sorted(slugs(response)) == ["listed", "mine"]
    assert set(response.data["results"][0]) == {"id", "name", "slug", "logo_url"}
    searched = client_for(staff).get(reverse(DIRECTORY), {"search": "LIST"})
    assert slugs(searched) == ["listed"]


def test_directory_refuses_accounts_that_run_no_events():
    org("listed", is_discoverable=True)
    plain = account("plain-account")
    assert client_for(plain).get(reverse(DIRECTORY)).status_code == 403
    assert APIClient().get(reverse(DIRECTORY)).status_code in (401, 403)


def test_directory_admits_organization_event_managers():
    outsider = account("org-event-runner")
    member(org("runner-org"), outsider, [rbac.Action.MANAGE_EVENTS])
    org("listed", is_discoverable=True)
    response = client_for(outsider).get(reverse(DIRECTORY))
    assert response.status_code == 200 and "listed" in slugs(response)


def test_discoverability_is_off_by_default_and_owner_toggled():
    organization = org("toggle-org")
    assert organization.is_discoverable is False
    owner = account("org-owner")
    OrganizationMembership.objects.create(organization=organization, user=owner,
                                          governance_actions=["manage_organization_profile"])
    url = reverse("admin-organization-detail", kwargs={"pk": organization.pk})
    response = client_for(owner).patch(url, {"is_discoverable": True}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["is_discoverable"] is True
    organization.refresh_from_db()
    assert organization.is_discoverable is True
    assert AuditLog.objects.filter(action="organization.profile_updated", meta__fields=["is_discoverable"]).exists()


# -- Partner makerspace directory -------------------------------------------------------

def test_partner_directory_is_the_public_directory_plus_managed_spaces():
    host = event_space("partner-host")
    staff = make_staff(host)
    listed = event_space("listed-space")
    listed.public_site_enabled = True
    listed.save(update_fields=["public_site_enabled"])
    hidden = event_space("hidden-space")
    hidden.public_site_enabled = False
    hidden.save(update_fields=["public_site_enabled"])
    no_events = event_space("no-events-space")
    no_events.public_site_enabled = True
    no_events.enabled_modules = [key for key in no_events.enabled_modules if key != "events"]
    no_events.save(update_fields=["public_site_enabled", "enabled_modules"])

    response = client_for(staff).get(reverse(PARTNERS), {"exclude": host.pk})
    assert response.status_code == 200
    assert slugs(response) == ["listed-space"]
    host.public_site_enabled = False
    host.save(update_fields=["public_site_enabled"])
    # Not publicly listed, but the actor manages events there.
    including_host = client_for(staff).get(reverse(PARTNERS))
    assert sorted(slugs(including_host)) == ["listed-space", "partner-host"]


# -- Organizers, audience and partners at creation --------------------------------------

def test_create_applies_organizers_audience_and_partners_in_one_transaction():
    host = event_space("create-host")
    host.enabled_features += [FEATURE]
    host.save(update_fields=["enabled_features"])
    staff = make_staff(host)
    own = org("own-org")
    member(own, staff)
    audience = org("audience-org", is_discoverable=True)
    partner = event_space("create-partner")

    response = client_for(staff).post(create_url(host), payload(
        registration_audience=AUDIENCE, organization_ids=[own.pk],
        audience_organization_ids=[audience.pk], collaborator_slugs=[partner.slug],
    ), format="json")

    assert response.status_code == 201, response.data
    event = Event.objects.get(pk=response.data["id"])
    assert [row["id"] for row in response.data["organizers"]] == [own.pk]
    assert [row["id"] for row in response.data["audience_organizations"]] == [audience.pk]
    assert list(EventCollaborator.objects.filter(event=event).values_list("makerspace_id", "status")) == [(partner.pk, "invited")]
    assert candidate_ids(event) >= {own.pk, audience.pk}
    actions = set(AuditLog.objects.filter(target_id=str(event.pk)).values_list("action", flat=True))
    assert {"event.created", "event.organizers_updated", "event.audience_organizations_updated",
            "event.collaborators_changed"} <= actions


@pytest.mark.parametrize("extra", ["foreign_organizer", "unknown_partner", "hidden_audience", "host_partner"])
def test_any_refusal_at_creation_creates_nothing(extra):
    host = event_space("refuse-host")
    staff = make_staff(host)
    values = {
        "foreign_organizer": {"organization_ids": [org("not-mine").pk]},
        "unknown_partner": {"collaborator_slugs": ["no-such-space"]},
        "hidden_audience": {"audience_organization_ids": [org("hidden-org").pk]},
        "host_partner": {"collaborator_slugs": [host.slug]},
    }[extra]
    response = client_for(staff).post(create_url(host), payload(**values), format="json")
    assert response.status_code in (400, 403), response.data
    assert not Event.objects.exists()
    assert not EventOrganizer.objects.exists() and not EventAudienceOrganization.objects.exists()


def test_create_rejects_duplicate_ids_and_patch_refuses_create_only_fields():
    host = event_space("dupe-host")
    staff = make_staff(host)
    own = org("dupe-org")
    member(own, staff)
    duplicate = client_for(staff).post(create_url(host), payload(organization_ids=[own.pk, own.pk]), format="json")
    assert duplicate.status_code == 400 and "organization_ids" in duplicate.data
    event = open_event(host)
    patched = client_for(staff).patch(reverse("admin-event-detail", kwargs={"pk": event.pk}),
                                      {"organization_ids": [own.pk]}, format="json")
    assert patched.status_code == 400


# -- Audience organizations -------------------------------------------------------------

def audience_event():
    host = event_space("aud-host")
    host.enabled_features += [FEATURE]
    host.save(update_fields=["enabled_features"])
    return host, make_staff(host), open_event(host, AUDIENCE)


def test_manager_replaces_audience_and_it_is_audited():
    host, staff, event = audience_event()
    first, second = org("first-aud", is_discoverable=True), org("second-aud", is_discoverable=True)
    response = client_for(staff).put(audience_url(event), {"organization_ids": [first.pk, second.pk]}, format="json")
    assert response.status_code == 200, response.data
    assert [row["slug"] for row in response.data["audience_organizations"]] == ["first-aud", "second-aud"]
    response = client_for(staff).put(audience_url(event), {"organization_ids": [second.pk]}, format="json")
    assert [row["id"] for row in response.data["audience_organizations"]] == [second.pk]
    audits = AuditLog.objects.filter(action="event.audience_organizations_updated", target_id=str(event.pk)).order_by("pk")
    assert [row.meta["organization_ids"] for row in audits] == [sorted([first.pk, second.pk]), [second.pk]]
    # Re-sending the same set is a no-op, not another audit row.
    client_for(staff).put(audience_url(event), {"organization_ids": [second.pk]}, format="json")
    assert audits.count() == 2


def test_retained_audience_organization_survives_losing_discoverability():
    _, staff, event = audience_event()
    kept = org("kept-aud", is_discoverable=True)
    client_for(staff).put(audience_url(event), {"organization_ids": [kept.pk]}, format="json")
    Organization.objects.filter(pk=kept.pk).update(is_discoverable=False)
    fresh = org("fresh-hidden")
    assert client_for(staff).put(audience_url(event), {"organization_ids": [kept.pk]}, format="json").status_code == 200
    refused = client_for(staff).put(audience_url(event), {"organization_ids": [kept.pk, fresh.pk]}, format="json")
    assert refused.status_code == 400
    assert list(EventAudienceOrganization.objects.values_list("organization_id", flat=True)) == [kept.pk]


@pytest.mark.parametrize(("permission", "status"), [("edit_details", 200), ("check_in", 403), ("manage_registrations", 403)])
def test_audience_permission_matrix_for_event_grantees(permission, status):
    host, staff, event = audience_event()
    grantee = account(f"aud-{permission}")
    create_manual_grant(makerspace=host, event=event, user=grantee, granted_by=staff, permissions=[permission])
    target = org(f"aud-{permission.replace('_', '-')}", is_discoverable=True)
    response = client_for(grantee).put(audience_url(event), {"organization_ids": [target.pk]}, format="json")
    assert response.status_code == status


def test_other_tenant_staff_cannot_touch_the_audience():
    _, _, event = audience_event()
    stranger = make_staff(event_space("aud-other"))
    target = org("aud-stranger", is_discoverable=True)
    response = client_for(stranger).put(audience_url(event), {"organization_ids": [target.pk]}, format="json")
    assert response.status_code == 404
    assert not EventAudienceOrganization.objects.exists()


def test_terminal_event_audience_is_frozen():
    _, staff, event = audience_event()
    Event.objects.filter(pk=event.pk).update(status=Event.Status.CANCELLED)
    target = org("aud-frozen", is_discoverable=True)
    response = client_for(staff).put(audience_url(event), {"organization_ids": [target.pk]}, format="json")
    assert response.status_code in (403, 409)
    assert not EventAudienceOrganization.objects.exists()


def test_audience_admits_members_but_grants_no_management_authority():
    _, staff, event = audience_event()
    target = org("aud-admit", is_discoverable=True)
    attendee = account("aud-attendee")
    member(target, attendee, [rbac.Action.MANAGE_EVENTS])
    with pytest.raises(Exception):
        require_organization_audience(event, attendee)

    client_for(staff).put(audience_url(event), {"organization_ids": [target.pk]}, format="json")
    event.refresh_from_db()
    require_organization_audience(event, attendee)  # admitted now
    assert not event_authority.can(attendee, event, None)
    assert not event_authority.can(attendee, event, "view")
    detail = client_for(attendee).get(reverse("admin-event-detail", kwargs={"pk": event.pk}))
    assert detail.status_code in (403, 404)
