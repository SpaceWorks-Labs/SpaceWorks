"""Leaks closed by the 0.12.0 API role-scoping audit, one regression each.

See handover/reports/API-ROLE-SCOPING-AUDIT-0.12.0.md for the route matrix. Each test names
the role that used to read or reach something outside its area.
"""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.events.models import Event, EventRegistration
from apps.machines import supervised
from apps.machines.models import EventInductionLink, Machine
from apps.maintenance.incidents import services as incidents
from apps.maintenance.incidents.models import Incident
from apps.makerspaces.models import Makerspace
from apps.operations.models_report_schedules import ReportSchedule
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_schedule_reach import recipient_reaches
from apps.shop.event_offers import staff_rows
from tests.events.checkin_helpers import make_event, register
from tests.events.ticketing_helpers import open_event
from tests.fixed_roles.helpers import staff_account
from tests.machines.certification_helpers import _certification, _machine_type, _manager, _member, _space
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


# Event equipment plan: no exact stock through repeated dry runs (#214b) ---------------------

@pytest.mark.parametrize("counts,quantity,free,expected", [
    (False, 9, 2, "ok"),      # coarse: something is free, the exact figure stays hidden
    (False, 1, 0, "short"),
    (True, 9, 2, "short"),    # inventory viewers keep the exact verdict
    (True, 2, 2, "ok"),
])
def test_plan_totals_never_binary_search_the_free_count(counts, quantity, free, expected):
    from apps.events.equipment_window import _totals
    figures = {7: {"free": free, "lendable": 5, "committed": 0, "back_before_window": 0}}
    rows = _totals([{"product_id": 7, "quantity": quantity}], [{"registration_id": 1, "lines": None}],
                   figures, counts)
    assert rows[0]["status"] == expected and ("free" in rows[0]) is counts


# Shop event offers: drafts are the events area's unpublished work ---------------------------

def _shop_space(slug):
    from tests.shop.helpers import shop_space, switch
    return switch(shop_space(slug, "shop.online", "shop.event_pickup"), modules=("events",))


def test_shop_staff_never_see_draft_events_but_event_staff_do():
    from tests.shop.helpers import manager, shop_manager
    space = _shop_space("scope0120-shop")
    published, draft = open_event(space), open_event(space)
    Event.objects.filter(pk=draft.pk).update(status=Event.Status.DRAFT, title="Secret launch")
    seller = shop_manager(space)
    assert {row["id"] for row in staff_rows(space, seller)} == {published.pk}
    assert {row["id"] for row in staff_rows(space, manager(space))} == {published.pk, draft.pk}
    # The PUT path shares the same event set: a seller cannot attach offers to the draft either.
    from apps.shop.errors import ShopRefused
    from apps.shop.event_offers import set_offers
    with pytest.raises(ShopRefused):
        set_offers(space, draft.pk, [], actor=seller)


# Induction overview: no attendee list without the reader's own induction link ---------------

def _machines_world(slug):
    space = _space(slug, modules=("machines", "events"))
    space.enabled_features = sorted(set(space.enabled_features or [])
                                    | {"machines.induction_events", "machines.supervised_sessions"})
    space.save(update_fields=["enabled_features"])
    laser, lathe = _machine_type(space, "Laser"), _machine_type(space, "Lathe")
    machine = Machine.objects.create(makerspace=space, machine_type=laser, name="Laser A")
    laser_mgr, _ = _manager(space, f"{slug}-laser", laser)
    lathe_mgr, _ = _manager(space, f"{slug}-lathe", lathe)
    return space, laser, lathe, machine, laser_mgr, lathe_mgr


def _attended_event(space, user):
    now = timezone.now()
    event = make_event(space, starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1))
    register(event, user, status=EventRegistration.Status.ATTENDED)
    return event


@pytest.mark.skip(reason="decision 319 addendum / 329: the induction HTTP surface is retired and answers 410 certifications_retired to every call (apps/machines/retired.py)")
def test_induction_overview_hides_attendees_of_events_the_reader_has_no_link_on():
    space, laser, lathe, _machine, laser_mgr, lathe_mgr = _machines_world("scope0120-ind")
    attendee, _ = _member(space, "scope0120-ind-attendee")
    event = _attended_event(space, attendee)
    url = f"/api/v1/admin/makerspaces/{space.pk}/events/{event.pk}/induction"
    unlinked = authenticated_client(laser_mgr).get(url)
    assert unlinked.status_code == 200 and unlinked.json()["attendees"] == []
    EventInductionLink.objects.create(makerspace=space, event=event, certification_type=_certification(space, laser))
    linked = authenticated_client(laser_mgr).get(url).json()
    assert [row["user_id"] for row in linked["attendees"]] == [attendee.pk]
    # Another type's manager still reads no attendee of the laser induction.
    assert authenticated_client(lathe_mgr).get(url).json()["attendees"] == []


# Supervised session: the people picker never reaches an unrelated event's registrants -------

def test_supervised_session_binds_only_an_event_the_instructor_runs_or_an_induction():
    space, laser, _lathe, machine, laser_mgr, _ = _machines_world("scope0120-sup")
    unrelated = make_event(space)
    with pytest.raises(ValidationError):
        supervised.open_session(machine, laser_mgr, event=unrelated)
    EventInductionLink.objects.create(makerspace=space, event=unrelated, certification_type=_certification(space, laser))
    session = supervised.open_session(machine, laser_mgr, event=unrelated)
    assert session.event_id == unrelated.pk


# Incidents: triage never moves an incident out of the actor's area; ids stay in the space ----

def test_incident_triage_cannot_push_an_incident_into_another_area():
    space, laser, _lathe, machine, laser_mgr, _ = _machines_world("scope0120-inc")
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_features=sorted(set(space.enabled_features) | {"safety.incidents"}))
    space.refresh_from_db()
    reporter, _ = _member(space, "scope0120-inc-reporter")
    incident = incidents.report(reporter, space, title="Spark", machine=machine)
    with pytest.raises(PermissionDenied):
        incidents.update(laser_mgr, incident, machine=None, area="lending")
    incident.refresh_from_db()
    assert incident.area == Incident.Area.MACHINES and incident.machine_id == machine.pk
    foreign_space = _space("scope0120-inc-foreign", modules=("machines",))
    foreign = Machine.objects.create(makerspace=foreign_space, machine_type=_machine_type(foreign_space), name="X")
    client = authenticated_client(reporter)
    response = client.post(f"/api/v1/member/makerspaces/{space.pk}/incidents",
                           {"title": "Probe", "machine_id": foreign.pk}, format="json")
    assert response.status_code == 404  # never a 400 confirming the id exists elsewhere


# Report schedules: a file built with the creator's reach stays with the creator's peers -----

def _reports_space(slug):
    space = make_space(slug)
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_modules=sorted(set(space.enabled_modules or []) | {"reports", "request_workflow"}))
    space.refresh_from_db()
    return space


def test_audit_schedule_is_managed_and_received_only_within_the_creators_reach():
    space = _reports_space("scope0120-sched")
    head = staff_account(space, "scope0120-sched-sm", "space_manager")
    stock = staff_account(space, "scope0120-sched-im", "inventory_manager")
    row = ReportSchedule.objects.create(makerspace=space, created_by=head, report_key="audit-activity",
                                        next_run_at=timezone.now() + timedelta(days=1))
    listed = authenticated_client(stock).get(reverse("report-schedules", args=[space.pk]))
    assert listed.status_code == 200, listed.content
    items = listed.data["results"] if isinstance(listed.data, dict) else listed.data
    assert row.pk not in {item["id"] for item in items}
    assert authenticated_client(stock).post(reverse("report-schedule-run-now", args=[row.pk])).status_code == 404
    assert authenticated_client(stock).patch(reverse("report-schedule-detail", args=[row.pk]),
                                             {"is_active": False}, format="json").status_code == 404
    audit = REPORT_REGISTRY["audit-activity"]
    assert not recipient_reaches(stock, row, audit)
    assert recipient_reaches(head, row, audit)
    # A report that does not narrow by its reader still reaches every holder of its action.
    lending = ReportSchedule.objects.create(makerspace=space, created_by=head, report_key="most-lent",
                                            next_run_at=timezone.now() + timedelta(days=1))
    assert recipient_reaches(stock, lending, REPORT_REGISTRY["most-lent"])
    # The Inventory Manager's own schedule stays theirs, and the Space Manager can manage it.
    # A schedule must name a recipient to be updated through the API (a recipient-less row is refused 400).
    own = ReportSchedule.objects.create(makerspace=space, created_by=stock, report_key="most-lent",
                                        recipient_roles=["inventory_manager"], next_run_at=timezone.now() + timedelta(days=1))
    assert authenticated_client(head).patch(reverse("report-schedule-detail", args=[own.pk]),
                                            {"is_active": False}, format="json").status_code == 200


def test_type_scoped_machine_manager_does_not_receive_a_wider_machine_file():
    space = _space("scope0120-sched-mm", modules=("machines", "reports"))
    laser = _machine_type(space, "Laser")
    head = staff_account(space, "scope0120-sched-mm-sm", "space_manager")
    laser_mgr = staff_account(space, "scope0120-sched-mm-laser", "machine_manager", machine_types=[laser])
    row = ReportSchedule.objects.create(makerspace=space, created_by=head, report_key="machine-usage",
                                        next_run_at=timezone.now() + timedelta(days=1))
    assert not recipient_reaches(laser_mgr, row, REPORT_REGISTRY["machine-usage"])
    own = ReportSchedule.objects.create(makerspace=space, created_by=laser_mgr, report_key="machine-usage",
                                        next_run_at=timezone.now() + timedelta(days=1))
    assert recipient_reaches(head, own, REPORT_REGISTRY["machine-usage"])


# Decision 224(a): reports are keyed to their own area, not to the VIEW_AUDIT default ---------

def _effective(slug):
    from tests.fixed_roles.test_role_screen_scoping import _effective as effective
    return effective(slug)


@pytest.mark.parametrize("key,action", [
    ("fablab-health", "manage_machines"), ("printer-service", "manage_machines"),
    ("certification-coverage", "manage_machines"), ("member-activity", "manage_members"),
    ("membership-growth", "manage_members"), ("member-retention", "manage_members"),
    ("community-engagement", "manage_members"), ("join-funnel", "manage_members"),
])
def test_area_reports_need_their_own_area_action(key, action):
    from apps.operations.report_types import definition_actions
    assert set(definition_actions(REPORT_REGISTRY[key])) == {action}
    assert action in _effective("space_manager")  # the Space Manager sees all
    assert action not in _effective("inventory_manager")


def test_report_catalog_lists_each_role_only_its_own_areas_reports():
    space = _reports_space("scope224-catalog")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"membership", "machines", "printing", "events", "bookings"})
    space.save(update_fields=["enabled_modules"])
    stock = staff_account(space, "scope224-im", "inventory_manager")
    machines = staff_account(space, "scope224-mm", "machine_manager")
    head = staff_account(space, "scope224-sm", "space_manager")

    def listed(user):
        response = authenticated_client(user).get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog")
        assert response.status_code == 200, response.content
        return {row["key"] for row in response.json()["results"]}

    area_keys = {"member-activity", "membership-growth", "member-retention", "community-engagement", "join-funnel",
                 "fablab-health", "printer-service", "certification-coverage"}
    assert not area_keys & listed(stock)
    assert "fablab-health" in listed(machines)
    # Decision 329(b): certification-coverage is retired history, listed only for a space that has
    # certification records.
    assert "certification-coverage" not in listed(machines)
    _certification(space, _machine_type(space, "Laser"))
    assert "certification-coverage" in listed(machines)
    assert not {"member-activity", "membership-growth", "join-funnel"} & listed(machines)
    assert {"member-activity", "membership-growth", "fablab-health"} <= listed(head)
    # Direct requests are refused with 403 as well as hidden from the list.
    for key in ("fablab-health", "member-activity"):
        assert authenticated_client(stock).get(
            f"/api/v1/admin/makerspace/{space.pk}/analytics/{key}").status_code == 403
        assert authenticated_client(stock).get(
            f"/api/v1/admin/makerspace/{space.pk}/reports/{key}/export").status_code == 403
    # Decision 248 / IN8 supersedes 224(a) for the accountability page: the Inventory Manager reads the
    # overdue and repeat-damage rows read-only, while restrictions and problem reports stay manage_members'.
    stock_view = authenticated_client(stock).get(f"/api/v1/admin/makerspace/{space.pk}/accountability")
    assert stock_view.status_code == 200, stock_view.content
    assert stock_view.json()["restrictions"] == [] and stock_view.json()["problem_reports"] == []
    # Neither manage_members nor view_inventory: the scoped resolver refuses without revealing the page (404).
    assert authenticated_client(machines).get(f"/api/v1/admin/makerspace/{space.pk}/accountability").status_code == 404
    assert authenticated_client(head).get(f"/api/v1/admin/makerspace/{space.pk}/accountability").status_code == 200


def test_scheduled_fablab_health_reaches_only_holders_of_the_machines_action():
    from apps.operations.report_schedule_rules import recipient_emails
    space = _reports_space("scope224-recipients")
    head = staff_account(space, "scope224-r-sm", "space_manager")
    stock = staff_account(space, "scope224-r-im", "inventory_manager")
    row = ReportSchedule.objects.create(makerspace=space, created_by=head, report_key="fablab-health",
                                        recipient_roles=["inventory_manager", "space_manager"],
                                        next_run_at=timezone.now() + timedelta(days=1))
    emails = recipient_emails(row, REPORT_REGISTRY["fablab-health"])
    assert head.email in emails and stock.email not in emails


# Decision 224(b): an induction link also needs authority on the event ------------------------

@pytest.mark.skip(reason="decision 319 addendum / 329: the induction HTTP surface is retired and answers 410 certifications_retired to every call (apps/machines/retired.py)")
def test_induction_link_needs_event_authority_as_well_as_machine_authority():
    space, laser, _lathe, _machine, laser_mgr, _ = _machines_world("scope224-ind")
    event = make_event(space)
    cert = _certification(space, laser)
    url = f"/api/v1/admin/makerspaces/{space.pk}/events/{event.pk}/induction"
    refused = authenticated_client(laser_mgr).post(url, {"certification_type_id": cert.pk}, format="json")
    assert refused.status_code == 403
    assert not EventInductionLink.objects.filter(event=event).exists()
    both = staff_account(space, "scope224-ind-both", "event_manager", "machine_manager", machine_types=[laser])
    assert authenticated_client(both).post(url, {"certification_type_id": cert.pk}, format="json").status_code == 201
    only_events = staff_account(space, "scope224-ind-ev", "event_manager")
    assert authenticated_client(only_events).post(url, {"certification_type_id": cert.pk}, format="json").status_code == 403


# Decision 224(c): payee/payout money is session-only everywhere ------------------------------

def test_payout_session_helpers_hide_payout_columns_and_reports():
    from types import SimpleNamespace
    from apps.payments.payout_session import full_session, is_payout_report, strip_payout_columns
    assert full_session(SimpleNamespace())
    assert not full_session(SimpleNamespace(person_credential=object()))
    assert not full_session(SimpleNamespace(api_client=object()))
    row = {"currency": "INR", "income": 1, "payouts": 2, "money_out": 3, "net": -2, "budget_left": 5}
    assert strip_payout_columns([row]) == [{"currency": "INR", "income": 1}]
    for key in ("event-finance", "prizes-owed", "income-spending", "finance-events"):
        assert is_payout_report(REPORT_REGISTRY[key]), key
    assert not is_payout_report(REPORT_REGISTRY["most-lent"])


@pytest.mark.parametrize("kind", ["pat", "oauth"])
def test_delegated_credentials_read_no_event_payout_money(settings, kind):
    from tests.api_r2.test_person_credentials import _bearer
    from tests.events.collab_helpers import client_for
    from tests.hardware_requests.test_phase2_person_credential_boundary import delegated_credential
    from tests.payments.test_event_linked_finance_item08 import _space as finance_space
    from tests.return_helpers import make_member
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.HMAC_PROTECTED_PATH_PREFIXES = ["/api/v1/public/"]
    space = finance_space(f"scope224-pay-{kind}", modules=("events", "bookings"))
    event = open_event(space)
    manager = make_member(f"scope224-pay-{kind}-sm", space)
    base = f"/api/v1/admin/makerspace/{space.pk}/finance"
    assert client_for(manager).get(f"{base}/events/{event.pk}").status_code == 200
    assert client_for(manager).get(f"{base}/summary").status_code == 200
    api = _bearer(delegated_credential(kind, manager, space))
    assert api.get(f"{base}/events/{event.pk}").status_code == 403
    token_summary = api.get(f"{base}/summary")
    if token_summary.status_code == 200:  # when the route is delegable, payout figures are stripped
        assert all("payouts" not in row and "net" not in row for row in token_summary.json()["rows"])
    for key in ("event-finance", "prizes-owed"):
        assert api.get(f"/api/v1/admin/makerspace/{space.pk}/reports/{key}/export").status_code == 403


# Decision 224(d): handout-only roles get a counter-only API -----------------------------------

def test_handout_only_role_is_refused_inventory_wide_reports_and_exports():
    space = _reports_space("scope224-desk")
    desk = staff_account(space, "scope224-desk-h", "handover")
    stock = staff_account(space, "scope224-desk-im", "inventory_manager")
    base = f"/api/v1/admin/makerspace/{space.pk}"
    client = authenticated_client(desk)
    for path in ("reports/catalog", "analytics/loan-throughput", "reports/stock-health/export",
                 "ledger", "ledger/export", "accountability"):
        assert client.get(f"{base}/{path}").status_code in {403, 404}, path
    assert authenticated_client(stock).get(f"{base}/reports/catalog").status_code == 200
