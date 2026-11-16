"""Page authority has constant query cost and matches the detail projection."""

from tests.account_split.sweep_g2_helpers import staff_user

from datetime import time, timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events import event_authority
from apps.events.event_permissions import PERMISSIONS
from apps.events.models import Event, EventOrganizer, EventSeries, EventSeriesOrganizer, EventStaffGrant
from apps.events.serializers_admin import EventAdminSerializer
from apps.events.serializers_event_authority import EventAuthorityFields, event_list_context
from apps.events.serializers_series import EventSeriesSummarySerializer
from apps.makerspaces.models import MakerspaceMembership
from apps.organizations.models import Organization, OrganizationMembership
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space

pytestmark = pytest.mark.django_db


class _EventProjection(EventAdminSerializer):
    # Measure the changed authority fields, independently of unrelated feature,
    # image and registration projections in the full response.
    class Meta(EventAdminSerializer.Meta):
        fields = ("staff_permissions", "can_manage_staff")


class _SeriesProjection(EventSeriesSummarySerializer):
    class Meta(EventSeriesSummarySerializer.Meta):
        fields = ("staff_permissions", "can_manage_staff")


def _page_fixture(size, source):
    space = event_space("authority-page")
    manager = make_staff(space)
    user = manager if source == "tenant" else account("page-reader")
    start = timezone.now() + timedelta(days=1)
    series = EventSeries.objects.bulk_create([
        EventSeries(
            makerspace=space, title=f"Series {index}", recurrence_timezone="UTC",
            dtstart_local_date=start.date(), dtstart_local_time=time(12),
            recurrence_rule="FREQ=DAILY;COUNT=1", duration_minutes=60,
        ) for index in range(size)
    ])
    events = Event.objects.bulk_create([
        Event(makerspace=space, series=row,
              series_occurrence_key=f"{row.revision}:{start:%Y%m%dT%H%M%S}",
              series_revision=row.revision, title=row.title, starts_at=start,
              ends_at=start + timedelta(hours=1)) for row in series
    ])
    if source in ("organizer", "series_organizer"):
        org = Organization.objects.create(name="Page organizers", slug="page-organizers")
        OrganizationMembership.objects.create(
            organization=org, user=user, granted_actions=["manage_events"],
        )
        if source == "organizer":
            EventOrganizer.objects.bulk_create([
                EventOrganizer(event=row, organization=org) for row in events
            ])
        else:
            EventSeriesOrganizer.objects.bulk_create([
                EventSeriesOrganizer(series=row, organization=org) for row in series
            ])
    elif source == "grant":
        from tests.events.manual_grant_fixture import bulk_manual_sources
        bulk_manual_sources(EventStaffGrant.objects.bulk_create([
            EventStaffGrant(makerspace=space, series=row, user=user,
                            granted_by=manager, permissions=["check_in"])
            for row in series
        ] + [
            EventStaffGrant(makerspace=space, event=row, user=user,
                            granted_by=manager, permissions=["edit_details"])
            for row in events
        ]))
    return space, user, events, series


@pytest.mark.parametrize("source", ["tenant", "organizer", "series_organizer", "grant"])
@pytest.mark.parametrize("kind", ["event", "series"])
def test_page_authority_queries_do_not_grow_with_page_size(source, kind):
    _, user, events, series = _page_fixture(200, source)
    rows = events if kind == "event" else series
    serializer = _EventProjection if kind == "event" else _SeriesProjection
    counts = []
    for page_size in (1, 24, 200):
        page = rows[:page_size]
        request = SimpleNamespace(user=user)
        with CaptureQueriesContext(connection) as queries:
            context = event_list_context(request, page)
            data = serializer(page, many=True, context=context).data
        counts.append(len(queries))
        # 19 = the base 16 + 1 entitlement candidate list + the live issuer's RBAC check
        # (decided once per (issuer, tenant)); constant at every page size (approved).
        assert len(queries) <= 19
        manager = source in ("tenant", "series_organizer") or (source == "organizer" and kind == "event")
        permissions = list(PERMISSIONS) if manager else (
            [value for value in PERMISSIONS if value in {"check_in", "edit_details"}]
            if source == "grant" and kind == "event" else
            ["check_in"] if source == "grant" else []
        )
        assert all(row == {"can_manage_staff": manager, "staff_permissions": permissions} for row in data)
    assert counts[0] == counts[1] == counts[2]


@pytest.mark.parametrize("source", ["tenant", "organizer", "series_organizer", "grant"])
@pytest.mark.parametrize("state", ["active", "password_rotation", "restricted", "inactive", "anonymous",
                                   "archived", "module_off", "revoked", "superadmin"])
def test_page_projection_preserves_detail_semantics(source, state):
    space, user, events, series = _page_fixture(2, source)
    if state == "password_rotation":
        user.must_change_password = True
    elif state == "restricted":
        user.access_status = "restricted"
    elif state == "inactive":
        user.is_active = False
    elif state == "anonymous":
        user = AnonymousUser()
    elif state == "archived":
        space.archived_at = timezone.now()
        space.save(update_fields=["archived_at"])
    elif state == "module_off":
        space.enabled_modules = [key for key in space.enabled_modules if key != "events"]
        space.save(update_fields=["enabled_modules"])
    elif state == "revoked":
        EventStaffGrant.objects.filter(user=user).update(revoked_at=timezone.now())
    elif state == "superadmin":
        user = User.objects.create_superuser(username="page-root", password=None)
    request = SimpleNamespace(user=user)
    for rows in (events, series):
        context = event_list_context(request, rows)
        for row in rows:
            manager = event_authority.can_manage_grants(user, row)
            permissions = list(PERMISSIONS) if manager else event_authority.permissions_for(user, row)
            assert context["event_authority"][(row._meta.label, row.pk)] == (manager, permissions)


def test_page_grants_remain_scoped_when_occurrence_and_series_venues_differ():
    _, user, events, series = _page_fixture(1, "grant")
    other = event_space("other-authority-page")
    # Simulate a malformed/imported relation without modifying the series grant.
    Event.objects.filter(pk=events[0].pk).update(makerspace=other)
    event = Event.objects.get(pk=events[0].pk)
    context = event_list_context(SimpleNamespace(user=user), [event])
    assert context["event_authority"][(event._meta.label, event.pk)] == (False, [])
    # Existing manager checks consult the series' own tenant authority as well.
    user = staff_user(series[0].makerspace, "series-page-manager")
    context = event_list_context(SimpleNamespace(user=user), [event])
    assert event_authority.can_manage_grants(user, event)
    assert context["event_authority"][(event._meta.label, event.pk)] == (True, list(PERMISSIONS))


def test_empty_page_requires_no_authority_queries(django_assert_max_num_queries):
    request = SimpleNamespace(user=AnonymousUser())
    with django_assert_max_num_queries(0):
        assert event_list_context(request, []) == {
            "request": request, "event_authority": {},
        }


@pytest.mark.parametrize("route", ["admin-event-list-create", "admin-organized-event-list",
                                   "admin-accessible-events", "admin-event-series-list-create",
                                   "admin-event-series-occurrences"])
def test_every_list_passes_page_authority_through_serializer_context(route, monkeypatch):
    space, user, _, series = _page_fixture(2, "organizer")
    if route != "admin-organized-event-list":
        user = staff_user(space, "list-page-manager")
    original = EventAuthorityFields._authority
    projected = []

    def authority(self, obj):
        assert (obj._meta.label, obj.pk) in self.context["event_authority"]
        projected.append(obj.pk)
        return original(self, obj)

    monkeypatch.setattr(EventAuthorityFields, "_authority", authority)
    args = [space.pk] if route.endswith("list-create") else (
        [series[0].pk] if route.endswith("occurrences") else []
    )
    response = client_for(user).get(reverse(route, args=args))
    assert response.status_code == 200, response.data
    assert response.data["results"] and projected
    assert all(row["can_manage_staff"] and row["staff_permissions"] == list(PERMISSIONS)
               for row in response.data["results"])
