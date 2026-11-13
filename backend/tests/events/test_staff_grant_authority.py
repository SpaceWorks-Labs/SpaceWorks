from tests.events.manual_grant_fixture import create_manual_grant
from datetime import time

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts import rbac
from apps.events import event_authority
from apps.events.event_permissions import PERMISSIONS
from apps.events.models import Event, EventOrganizer, EventSeries, EventStaffGrant
from apps.events.services_staff_grants import revoke_grant
from apps.organizations.models import Organization, OrganizationMembership
from tests.events.collab_helpers import client_for
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("held", PERMISSIONS)
@pytest.mark.parametrize("requested", PERMISSIONS)
def test_permission_matrix_has_no_implied_grant_permissions(held, requested):
    _, _, user, event, _ = grant_fixture(held)
    assert event_authority.can(user, event, requested) is (held == requested)
    assert not event_authority.can_manage_grants(user, event)
    assert not event_authority.can(user, event, None)
    assert not event_authority.can(user, event, "manage_payments")


def test_grants_do_not_widen_tenant_scope_or_unrelated_events():
    space, _, user, event, _ = grant_fixture()
    sibling = open_event(space)
    foreign = open_event(event_space("grant-foreign"))
    assert rbac.effective_actions(user, space.pk) == set()
    assert not rbac.scope_by_makerspace(user, Event.objects.all()).exists()
    assert set(event_authority.events_for(user, "edit_details", Event.objects.all()).values_list("pk", flat=True)) == {event.pk}
    client = client_for(user)
    assert client.get(reverse("admin-event-detail", args=[event.pk])).status_code == 200
    for other in (sibling, foreign):
        assert client.get(reverse("admin-event-detail", args=[other.pk])).status_code == 404
    for tenant in (space, foreign.makerspace):
        assert client.get(reverse("admin-event-list-create", args=[tenant.pk])).status_code == 404


def test_revoked_grant_is_denied_on_the_next_request_even_with_same_actor():
    _, manager, user, event, grant = grant_fixture()
    client = client_for(user)
    url = reverse("admin-event-detail", args=[event.pk])
    assert client.get(url).status_code == 200
    revoke_grant(grant, actor=manager)
    assert client.get(url).status_code == 404
    assert not event_authority.can(user, event, "edit_details")


@pytest.mark.parametrize("state", ["archived", "module_off", "suspended", "inactive", "malformed_tenant"])
def test_grant_authority_rechecks_resource_and_account_gates(state):
    space, _, user, event, grant = grant_fixture()
    if state == "archived":
        space.archived_at = timezone.now()
        space.save(update_fields=["archived_at"])
    elif state == "module_off":
        space.enabled_modules.remove("events")
        space.save(update_fields=["enabled_modules"])
    elif state == "suspended":
        user.access_status = "suspended"
        user.save(update_fields=["access_status"])
    elif state == "inactive":
        user.is_active = False
        user.save(update_fields=["is_active"])
    else:
        grant.makerspace = event_space("malformed-grant")
        grant.save(update_fields=["makerspace"])
    event = Event.objects.select_related("makerspace").get(pk=event.pk)
    assert not event_authority.active_grants(user).exists()
    assert not event_authority.can(user, event, "edit_details")
    assert not event_authority.events_for(user, "edit_details", Event.objects.all()).exists()


def test_series_grant_applies_only_to_that_series_occurrences():
    space, manager, user, event, grant = grant_fixture("publish_schedule")
    series = EventSeries.objects.create(
        makerspace=space, title="Series", recurrence_timezone="UTC",
        dtstart_local_date=timezone.now().date(), dtstart_local_time=time(12),
        recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=60,
    )
    grant.event = None
    grant.series = series
    grant.save(update_fields=["event", "series"])
    from tests.events.staff_grant_helpers import set_grant_permissions
    set_grant_permissions(grant, list(grant.permissions))  # the source follows its grant
    event.series = series
    event.series_occurrence_key = "2026-10-15"
    event.series_revision = 1
    event.save(update_fields=["series", "series_occurrence_key", "series_revision"])
    sibling = open_event(space, series=series, series_occurrence_key="2026-10-16", series_revision=1)
    other = open_event(space)
    assert event_authority.can(user, series, "publish_schedule")
    assert set(event_authority.events_for(user, "publish_schedule", Event.objects.all()).values_list("pk", flat=True)) == {event.pk, sibling.pk}
    assert not event_authority.can(user, other, "publish_schedule")
    assert not event_authority.can_manage_grants(user, series)


def test_tenant_managers_and_existing_organizers_keep_all_permissions():
    _, manager, _, event, _ = grant_fixture()
    organizer = account("grant-organizer")
    organization = Organization.objects.create(name="Organizer", slug="grant-organizer")
    OrganizationMembership.objects.create(
        organization=organization, user=organizer, granted_actions=[rbac.Action.MANAGE_EVENTS],
    )
    EventOrganizer.objects.create(event=event, organization=organization)
    for actor in (manager, organizer):
        assert event_authority.can_manage_grants(actor, event)
        assert all(event_authority.can(actor, event, permission) for permission in PERMISSIONS)


def test_permission_validation_scope_constraint_and_live_uniqueness():
    space, manager, user, event, grant = grant_fixture()
    for values in ([], ["unknown"], ["check_in", "check_in"], "check_in"):
        grant.permissions = values
        with pytest.raises(ValidationError):
            grant.full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        create_manual_grant(makerspace=space, user=user, granted_by=manager, permissions=["check_in"])
    with pytest.raises(IntegrityError), transaction.atomic():
        create_manual_grant(makerspace=space, event=event, user=user, permissions=["check_in"])
    grant.revoked_at = timezone.now()
    grant.save(update_fields=["revoked_at"])
    create_manual_grant(makerspace=space, event=event, user=user, permissions=["check_in"])
