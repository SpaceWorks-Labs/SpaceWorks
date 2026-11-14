"""An event/series grant admits its actions while tenant settings and money policy stay staff-only."""
import pytest

from apps.audit.models import AuditLog
from apps.events.contributions.models_roles import EventGrantEntitlement
from apps.accounts import rbac
from apps.events.models import EventOrganizer, EventSeries, EventSeriesOrganizer, EventStaffGrant
from apps.organizations.models import Organization, OrganizationMembership
from tests.events.collab_helpers import client_for
from tests.events.ticketing_helpers import account
from tests.events.test_staff_surface_conditions_mod2b import NAMES, assert_restored, call, routes, world
from tests.refusal_helpers_mod2b import refused

pytestmark = pytest.mark.django_db
TENANT_ONLY = {"pass-types-list", "pass-types-create", "pass-types-patch", "embed-get", "embed-put",
               "switches-get", "switches-patch", "series-collab-get", "series-collab-put"}


@pytest.mark.parametrize("name", NAMES)
def test_manual_event_and_series_delegate_actions_and_tenant_authority_boundary(name):
    w = world("cx5-scoped-manual-" + name)
    actor = w.plain
    permissions = ["edit_details", "publish_schedule", "manage_registrations", "check_in"]
    for target in ({"event": w.event}, {"series": w.series}):
        grant = EventStaffGrant.objects.create(makerspace=w.space, user=actor, granted_by=w.staff,
                                                permissions=permissions, **target)
        EventGrantEntitlement.objects.create(makerspace=w.space, grant=grant, source_kind="manual",
                                               permissions=permissions, created_by=w.staff, **target)
    if name in TENANT_ONLY:
        before = AuditLog.objects.filter(makerspace=w.space).count()
        refused(call(actor, routes(w)[name]), 403, "permission_denied")
        assert AuditLog.objects.filter(makerspace=w.space).count() == before
    else:
        w.staff = actor
        assert_restored(w, name, routes(w)[name])


def organization_actor(event, role, *, series=None):
    """An outside organization organiser, or the second co-organising organization.

    Neither account has a venue membership or any manual EventStaffGrant. The
    membership's action and the organizer relationship are its only authority.
    """
    primary = Organization.objects.create(slug=f"cx5-primary-{event.pk}", name="Primary organizer")
    EventOrganizer.objects.create(event=event, organization=primary)
    if series is not None:
        EventSeriesOrganizer.objects.create(series=series, organization=primary)
    organization = primary
    if role == "coorganizer":
        organization = Organization.objects.create(slug=f"cx5-partner-{event.pk}", name="Co-organizer")
        EventOrganizer.objects.create(event=event, organization=organization)
        if series is not None:
            EventSeriesOrganizer.objects.create(series=series, organization=organization)
    actor = account(f"cx5-org-{role}-{event.pk}")
    OrganizationMembership.objects.create(organization=organization, user=actor,
        status="active", granted_actions=[rbac.Action.MANAGE_EVENTS])
    assert not EventStaffGrant.objects.filter(user=actor).exists()
    assert not rbac.can(actor, rbac.Action.MANAGE_EVENTS, event.makerspace_id)
    return actor


@pytest.mark.parametrize("role", ["organizer", "coorganizer"])
@pytest.mark.parametrize("name", NAMES)
def test_organization_organizers_use_resource_routes_without_tenant_authority(name, role):
    w = world("cx5-org-" + role + "-" + name)
    actor = organization_actor(w.event, role, series=w.series)
    before = AuditLog.objects.filter(makerspace=w.space).count()
    if name.startswith(("embed-", "switches-")):
        refused(call(actor, routes(w)[name]), 404, "not_found")
    elif name.startswith("pass-types-"):
        refused(call(actor, routes(w)[name]), 403, "permission_denied")
    else:
        w.staff = actor
        assert_restored(w, name, routes(w)[name])
        return
    assert AuditLog.objects.filter(makerspace=w.space).count() == before


@pytest.mark.parametrize("source", ["manual_event", "manual_series", "organization_event", "organization_series"])
def test_each_authority_source_independently_admits_only_its_event_or_series(source):
    w = world("cx5-source-" + source.replace("_", "-"))
    occurrence = w.series.occurrences.order_by("pk").first()
    assert occurrence is not None
    other_series = EventSeries.objects.create(makerspace=w.space, title="Unrelated series",
        recurrence_timezone="UTC", dtstart_local_date=w.series.dtstart_local_date,
        dtstart_local_time=w.series.dtstart_local_time, recurrence_rule="FREQ=DAILY;COUNT=1",
        duration_minutes=60)
    if source.startswith("manual"):
        actor = w.plain
        target = {"series": w.series} if source.endswith("series") else {"event": w.event}
        grant = EventStaffGrant.objects.create(makerspace=w.space, user=actor, granted_by=w.staff,
            permissions=["edit_details"], **target)
        EventGrantEntitlement.objects.create(makerspace=w.space, grant=grant, source_kind="manual",
            permissions=["edit_details"], created_by=w.staff, **target)
    else:
        # Build only the named relationship: there is no event+series union to mask a broken path.
        actor = account(f"cx5-source-actor-{w.event.pk}")
        organization = Organization.objects.create(slug=f"cx5-source-{w.event.pk}", name="Source organizer")
        OrganizationMembership.objects.create(organization=organization, user=actor,
            granted_actions=[rbac.Action.MANAGE_EVENTS])
        if source.endswith("series"):
            EventSeriesOrganizer.objects.create(series=w.series, organization=organization)
        else:
            EventOrganizer.objects.create(event=w.event, organization=organization)
    api = client_for(actor)
    admitted = occurrence if source.endswith("series") else w.event
    unrelated = w.event if source.endswith("series") else occurrence
    got = api.get(f"/api/v1/admin/events/{admitted.pk}/website/")
    assert got.status_code == 200, got.content
    status, code = (403, "permission_denied") if source.startswith("manual") else (404, "not_found")
    refused(api.get(f"/api/v1/admin/events/{unrelated.pk}/website/"), status, code)
    series_url = f"/api/v1/admin/event-series/{w.series.pk}/website/"
    if source.endswith("series"):
        assert api.get(series_url).status_code == 200
    else:
        refused(api.get(series_url), status, code)
    refused(api.get(f"/api/v1/admin/event-series/{other_series.pk}/website/"), status, code)
