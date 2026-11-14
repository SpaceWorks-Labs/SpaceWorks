"""Fixed area report URLs must contain the seeded activity, not an empty successful response."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.events.models import EventRegistration
from apps.machines.models import MachineUsageEntry
from apps.maintenance.models import MaintenanceLog
from tests.accounts.account_factories import make_membership
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports]

CASES = [(report, key) for report, keys in [
    ("machine-usage", ("reports", "machines")), ("event-attendance", ("reports", "events")),
    ("booking-utilization", ("reports", "bookings")),
    ("maintenance-activity", ("reports", "machines", "machines.maintenance")),
    ("member-activity", ("reports", "membership")), ("fablab-health", ("reports",)),
    ("payment-reconciliation", ("reports",)),
] for key in keys]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("report,key", CASES)
def test_area_report_url_restores_the_exact_domain_measure(native, report, key):
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    make_membership(actor, space)
    machine, event, room = objects["machine"], objects["event"], objects["room"]
    MachineUsageEntry.objects.create(machine=machine, hours=Decimal("1.25"), logged_by=actor)
    MaintenanceLog.objects.create(machine=machine, performed_by=actor, performed_at=timezone.now(),
                                   summary="Retained calibration", cost=Decimal("10.10"))
    EventRegistration.objects.create(event=event, member=actor, name="Retained attendee", status="attended")
    start = timezone.now() - timedelta(hours=3)
    Booking.objects.create(space=room, member=actor, name="Retained booker", email="g4-report-booker@example.test", starts_at=start,
                           ends_at=start + timedelta(hours=2), status="completed")
    if report == "payment-reconciliation":
        from tests.payments.test_refunds import paid_deposit
        paid_deposit(space, actor, status="pending", amount="12.50", intent=None)
    url = reverse(f"analytics-{report}", kwargs={"makerspace_id": space.pk})

    def check(response):
        rows = response.data["typed_rows"]
        if report == "machine-usage":
            row = next(r for r in rows if r["machine_id"] == machine.pk and r["measure"] == "manual")
            assert (row["machine_name"], row["manual_hours"]) == (machine.name, "1.25")
        elif report == "event-attendance":
            assert [(r["event_id"], r["registrations"], r["attended"]) for r in rows] == [(event.pk, 1, 1)]
        elif report == "booking-utilization":
            assert {r["space_id"] for r in rows} == {room.pk}
            assert sum(r["completed"] for r in rows) == 1
            assert sum(Decimal(r["reserved_hours"]) for r in rows) == Decimal("2.00")
        elif report == "maintenance-activity":
            row = next(r for r in rows if r["machine_id"] == machine.pk and r["period"] is not None)
            assert (row["log_count"], row["costed_log_count"], row["total_cost"]) == (1, 1, "10.10")
        elif report == "member-activity":
            assert [(r["makerspace_name"], r["active_members"]) for r in rows] == [(space.name, 1)]
        elif report == "fablab-health":
            assert len(rows) == 1
            assert (rows[0]["events_registrations"], rows[0]["bookings_non_cancelled"],
                    rows[0]["machines_active"], rows[0]["maintenance_logs"]) == (1, 1, 1, 1)
        else:
            assert len(rows) == 1
            assert (rows[0]["payment_count"], rows[0]["status"], rows[0]["amount_total"],
                    rows[0]["outstanding_amount"], rows[0]["refunded_amount"]) == (1, "pending", "12.50", "12.50", "0.00")
    foreign = outsider(native)
    # 481/494 applies to every fixed alias: they all carry makerspace_id.
    cycle(space, key, lambda: client.get(url), check,
          off=(404, "capability_disabled" if "." in key else "module_disabled"), foreign=lambda: foreign.get(url), foreign_native=native)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("report,key", [
    ("machine-usage", "machine_service"), ("machine-usage", "bookings"),
    ("fablab-health", "events"), ("fablab-health", "bookings"),
    ("fablab-health", "machines"), ("fablab-health", "machines.maintenance"),
])
def test_report_sections_hide_only_disabled_source_and_restore_retained_measures(native, report, key):
    from apps.machines.models import MachineServiceRequest, ServiceQueue
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    machine, event, room = objects["machine"], objects["event"], objects["room"]
    room.machine_type = machine.machine_type
    room.save(update_fields=["machine_type"])
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=machine.machine_type, name="G4 section queue")
    MachineServiceRequest.objects.create(makerspace=space, queue=queue, requester=actor, member=actor,
        assigned_machine=machine, title="Retained measured job", status="completed", actual_minutes=90,
        completed_at=timezone.now())
    MachineUsageEntry.objects.create(machine=machine, hours=Decimal("1.25"), logged_by=actor)
    MaintenanceLog.objects.create(machine=machine, performed_by=actor, performed_at=timezone.now(),
                                   summary="Retained section calibration", cost=Decimal("10.10"))
    EventRegistration.objects.create(event=event, member=actor, name="Retained section attendee", status="attended")
    start = timezone.now() - timedelta(hours=3)
    Booking.objects.create(space=room, member=actor, name="Retained measured booking", email="g4-report-booker@example.test", starts_at=start,
                           ends_at=start + timedelta(hours=2), status="completed")
    url = reverse(f"analytics-{report}", kwargs={"makerspace_id": space.pk})

    def measures(response, disabled):
        rows = response.data["typed_rows"]
        if report == "machine-usage":
            expected = {"manual": "1.25", "service": "1.50", "booked": "2.00"}
            if disabled:
                del expected["service" if key == "machine_service" else "booked"]
            assert {r["measure"]: r[r["measure"] + "_hours"] for r in rows} == expected
            assert all(r["entries"] == 1 for r in rows)
        else:
            assert len(rows) == 1
            sections = {"events": ("events_registrations", 1), "bookings": ("bookings_non_cancelled", 1),
                        "machines": ("machines_active", 1), "maintenance": ("maintenance_logs", 1)}
            hidden = {"maintenance"} if key == "machines.maintenance" else {"machines", "maintenance"} if key == "machines" else {key}
            for section, (field, value) in sections.items():
                enabled = not disabled or section not in hidden
                assert (rows[0][section + "_enabled"], rows[0][section + "_available"], rows[0][field]) == (
                    enabled, enabled, value if enabled else None)
    foreign = outsider(native)
    # Optional sections retain the URL's 200 policy; source rows must survive, not turn into a route refusal.
    cycle(space, key, lambda: client.get(url), lambda r: measures(r, False), off=(200, None),
          off_check=lambda r: measures(r, True), foreign=lambda: foreign.get(url), foreign_native=native)
