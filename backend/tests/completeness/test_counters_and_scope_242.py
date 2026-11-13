"""Decision 242: dashboard bug fixes, "Waiting on me", schedule layers, member 360, incident and work-order reach."""
import pytest
from django.urls import reverse

from apps.operations.dashboard_attention import build_attention
from apps.operations.schedule import available_layers, build_schedule
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_accepted_request, make_product, make_space

pytestmark = pytest.mark.django_db

MODULES = ("machines", "machine_service", "events", "bookings", "request_workflow", "staff_admin", "reports", "shop")


def _space(slug):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules or []) | set(MODULES))
    space.save(update_fields=["enabled_modules"])
    return space


def _items(attention, area):
    return {row["key"]: row["count"] for group in attention["areas"] if group["key"] == area for row in group["items"]}


def test_direct_loan_is_counted_once_as_overdue_and_due_back_counts_are_server_side():
    from datetime import timedelta
    from django.utils import timezone
    from apps.hardware_requests.models import HardwareRequest
    from apps.operations.dashboard_counts import build_dashboard

    space = _space("c242-overdue")
    sm = staff_account(space, "c242-sm", "space_manager")
    loan = make_accepted_request(space, make_product(space), 1)
    HardwareRequest.objects.filter(pk=loan.pk).update(
        status="issued", return_due_at=timezone.now() - timedelta(days=1))
    counts = build_dashboard(space, actor=sm)
    assert counts["overdue_loans"] == 1
    assert {"due_today_loans", "due_soon_loans", "true_low_stock", "in_repair"} <= set(counts)


def test_attention_is_built_only_from_the_actors_own_actions():
    space = _space("c242-attention")
    sm = staff_account(space, "c242-att-sm", "space_manager")
    shop = staff_account(space, "c242-att-shop", "shop_manager")
    tech = staff_account(space, "c242-att-tech", "technician")
    event = staff_account(space, "c242-att-event", "event_manager")
    sm_areas = {g["key"] for g in build_attention(sm, space)["areas"]}
    assert {"lending", "machines", "events", "bookings", "shop", "people", "money"} <= sm_areas
    assert {g["key"] for g in build_attention(shop, space)["areas"]} <= {"shop", "money"}
    assert {g["key"] for g in build_attention(event, space)["areas"]} <= {"events", "money"}
    tech_items = _items(build_attention(tech, space), "machines")
    assert set(tech_items) == {"my_open_repairs", "my_work_orders"}  # never the managers' queues
    assert "money" not in {g["key"] for g in build_attention(tech, space)["areas"]}


def test_attention_route_and_dashboard_admit_shop_manager_and_technician():
    space = _space("c242-home")
    for slug, username in (("shop_manager", "c242-h-shop"), ("technician", "c242-h-tech")):
        person = staff_account(space, username, slug)
        client = authenticated_client(person)
        assert client.get(reverse("operations-dashboard", args=[space.pk])).status_code == 200
        assert client.get(reverse("operations-attention", args=[space.pk])).status_code == 200


def test_schedule_layers_follow_the_role_and_the_space_manager_sees_all():
    space = _space("c242-schedule")
    sm = staff_account(space, "c242-sch-sm", "space_manager")
    booking = staff_account(space, "c242-sch-bk", "booking_manager")
    event = staff_account(space, "c242-sch-ev", "event_manager")
    assert {"bookings", "events", "shifts", "machine_jobs", "maintenance"} <= set(available_layers(sm, space))
    assert "bookings" in available_layers(booking, space) and "events" not in available_layers(booking, space)
    assert available_layers(event, space) == ["events", "shifts"]
    assert build_schedule(booking, space)["layers"] == available_layers(booking, space)
    response = authenticated_client(sm).get(reverse("operations-schedule", args=[space.pk]) + "?layers=events")
    assert response.status_code == 200 and response.json()["layers"]


def test_member_360_shows_counts_everywhere_but_rows_only_for_managed_areas():
    space = _space("c242-360")
    member = staff_account(space, "c242-360-member", "member")
    people = staff_account(space, "c242-360-people", "space_manager")
    booking = staff_account(space, "c242-360-bk", "booking_manager")
    body = authenticated_client(people).get(reverse("admin-member-activity", args=[space.pk, member.pk]))
    assert body.status_code == 200 and not body.json()["errors"]
    assert all(area["rows_visible"] for area in body.json()["areas"] if area["area"] in {"lending", "bookings"})
    # Decision 248: counts are open to every staff role with an area action; rows only for managed areas.
    # A Booking Manager sees counts everywhere and rows only for bookings.
    response = authenticated_client(booking).get(reverse("admin-member-activity", args=[space.pk, member.pk]))
    assert response.status_code == 200
    by_area = {area["area"]: area for area in response.json()["areas"]}
    assert by_area["bookings"]["rows_visible"] is True
    assert by_area["lending"]["rows_visible"] is False and by_area["lending"]["rows"] is None


def test_technician_reads_incidents_on_covered_types_but_never_records_or_triages():
    from apps.maintenance.incidents import scope

    space = _space("c242-incident")
    tech = staff_account(space, "c242-inc-tech", "technician")
    handover = staff_account(space, "c242-inc-member", "member")
    assert scope.can_record(tech, space) is False
    assert scope.is_staff_reader(handover, space) is False  # Handover/members see none


def test_bulk_decision_is_all_or_nothing_and_names_the_failing_id():
    space = _space("c242-bulk")
    inventory = staff_account(space, "c242-bulk-inv", "inventory_manager")
    first = make_accepted_request(space, make_product(space), 1)
    response = authenticated_client(inventory).post(
        reverse("admin-bulk-requests", args=["reject"]), {"ids": [first.pk, 999999], "reason": "no"}, format="json")
    assert response.status_code == 409 and response.json()["failed_id"] in (first.pk, 999999)
    first.refresh_from_db()
    assert first.status == "accepted"  # nothing was changed


def test_platform_cross_space_routes_are_superadmin_only():
    from apps.accounts.models import User

    space = _space("c242-platform")
    manager = staff_account(space, "c242-plat-sm", "space_manager")
    root = User.objects.create_superuser("c242-root", "c242-root@example.test", None)
    for name in ("admin-platform-queues", "admin-platform-inbox"):
        assert authenticated_client(manager).get(reverse(name)).status_code in (401, 403)
    assert authenticated_client(manager).get(reverse("admin-platform-search") + "?q=abc").status_code in (401, 403)
    assert authenticated_client(manager).get(reverse("admin-platform-space-snapshot", args=[space.pk])).status_code in (401, 403)
    client = authenticated_client(root)
    rows = client.get(reverse("admin-platform-queues")).json()["spaces"]
    assert any(row["id"] == space.pk for row in rows)
    snapshot = client.get(reverse("admin-platform-space-snapshot", args=[space.pk])).json()
    assert snapshot["usage"]["resources"]  # usage is always shown, Own spaces included
    assert client.get(reverse("admin-platform-search") + "?q=ab").status_code == 400  # too short
    assert client.get(reverse("admin-platform-search") + "?q=c242-platform").json()["results"]
