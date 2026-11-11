"""L1: DY-61 report switches, DY-63 host picker and the #77 closed-for-now banner."""

import pytest
from django.db import transaction
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events.models import Event
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.makerspaces.settings_authority_writes import set_grants
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import event_space

pytestmark = pytest.mark.django_db(transaction=True)


@transaction.atomic
def event_manager(space, name="evm"):
    user = User.objects.create_user(username=f"{name}-{space.slug}", email=f"{name}-{space.slug}@example.test",
                                    access_status="active", account_kind="staff", staff_makerspace=space)
    MakerspaceMembership.objects.create(user=user, makerspace=space, role=MakerspaceMembership.Role.EVENT_MANAGER,
                                        assigned_role=MakerspaceRole.objects.get(makerspace=space, slug="event_manager"),
                                        status="active")
    return user


def reports_space(slug):
    space = event_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"reports"})
    space.save(update_fields=["enabled_modules"])
    return space


def switches(space):
    return f"/api/v1/admin/makerspaces/{space.pk}/events/report-switches/"


def test_dy61_event_manager_switches_report_keys_only_with_the_events_grant():
    space = reports_space("dy61")
    sm, manager = make_staff(space), event_manager(space)
    read = client_for(manager).get(switches(space))
    assert read.status_code == 200
    assert {row["key"]: row["editable"] for row in read.data["switches"]} == {
        "reports.event_pdf": False, "reports.event_exports": False}
    body = {"switches": {"reports.event_pdf": True}}
    refused = client_for(manager).patch(switches(space), body, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "setting_not_delegated"
    set_grants(sm, space, "events", [manager.pk])
    saved = client_for(manager).patch(switches(space), body, format="json")
    assert saved.status_code == 200
    space.refresh_from_db()
    assert "reports.event_pdf" in space.enabled_features
    row = AuditLog.objects.filter(action="settings.changed", meta__key="reports.event_pdf").get()
    assert row.meta["via"] == "module_grant" and row.meta["module"] == "events"


def test_dy61_space_manager_always_and_lock_blocks_the_grant():
    from apps.makerspaces.settings_authority_writes import set_lock
    space = reports_space("dy61b")
    sm, manager = make_staff(space), event_manager(space)
    set_grants(sm, space, "events", [manager.pk])
    set_lock(sm, space, "reports.event_exports", True)
    body = {"switches": {"reports.event_exports": True}}
    locked = client_for(manager).patch(switches(space), body, format="json")
    assert locked.status_code == 403 and locked.data["code"] == "setting_locked"
    assert client_for(sm).patch(switches(space), body, format="json").status_code == 200
    unknown = client_for(sm).patch(switches(space), {"switches": {"events.short_links": True}}, format="json")
    assert unknown.status_code == 400


def test_dy63_host_options_and_hosting_in_another_space_the_actor_runs_events_in():
    home, away = event_space("home63"), event_space("away63")
    root = User.objects.create_superuser(username="root63", role=User.Role.SUPERADMIN, is_superuser=True,
                                         is_staff=True, access_status=User.AccessStatus.ACTIVE)
    options = client_for(root).get("/api/v1/admin/events/host-options/")
    assert options.status_code == 200
    assert {"home63", "away63"} <= {row["slug"] for row in options.data}
    body = {"title": "Away jam", "starts_at": "2030-01-01T10:00:00Z", "ends_at": "2030-01-01T12:00:00Z",
            "host_makerspace_id": away.pk}
    created = client_for(root).post(f"/api/v1/admin/makerspaces/{home.pk}/events/", body, format="json")
    assert created.status_code == 201, created.data
    assert Event.objects.get(pk=created.data["id"]).makerspace_id == away.pk
    # A one-space Space Manager sees only their own space and cannot host elsewhere.
    sm = make_staff(home)
    assert [row["slug"] for row in client_for(sm).get("/api/v1/admin/events/host-options/").data] == ["home63"]
    assert client_for(sm).post(f"/api/v1/admin/makerspaces/{home.pk}/events/", body, format="json").status_code == 403


def notice_url(space):
    return f"/api/v1/admin/makerspace/{space.pk}/public-closed-notice"


def test_closed_notice_space_manager_only_audited_and_in_bootstrap():
    space = event_space("closed77")
    sm, manager = make_staff(space), event_manager(space)
    assert client_for(sm).get(notice_url(space)).status_code == 404  # switch off
    space.enabled_features += ["public_site.closed_notice"]
    space.save(update_fields=["enabled_features"])
    body = {"public_closed_notice": "Closed for renovation.", "public_reopens_on": "2099-01-15"}
    assert client_for(manager).put(notice_url(space), body, format="json").status_code in {403, 404}
    saved = client_for(sm).put(notice_url(space), body, format="json")
    assert saved.status_code == 200
    row = AuditLog.objects.get(action="makerspace.closed_notice_updated")
    assert row.meta["notice_set"] is True and row.meta["reopens_on"] == "2099-01-15"
    from apps.makerspaces.platform import bootstrap_payload
    payload = bootstrap_payload(Makerspace.objects.get(pk=space.pk))["makerspace"]
    assert payload["closed_notice"] == {"text": "Closed for renovation.", "reopens_on": "2099-01-15"}
    space.refresh_from_db()
    assert space.lifecycle_state == "active"
    space.enabled_features.remove("public_site.closed_notice")
    space.save(update_fields=["enabled_features"])
    assert "closed_notice" not in bootstrap_payload(Makerspace.objects.get(pk=space.pk))["makerspace"]
    assert Makerspace.objects.get(pk=space.pk).public_closed_notice == "Closed for renovation."
    assert APIClient().get(notice_url(space)).status_code in {401, 403}
