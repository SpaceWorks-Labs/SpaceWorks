"""Machines audit 0.12.0: per machine TYPE and per MACHINE, across the machine surfaces.

Owner question: "per machine and per type machine all good?" Report:
handover/reports/MACHINES-AUDIT-0.12.0.md (surface x role matrix).

Part A (per type) is one parametrized matrix over six personas in one space that runs a
laser type (Laser A) and a CNC type (CNC A):

* ``type_manager``  Machine Manager linked to the laser type only
* ``technician``    Technician whose in-house coverage names the laser type only
* ``full_manager``  Machine Manager linked to both types
* ``member``        plain member
* ``guest``         an account with no membership here
* ``minor``         a member recorded as a minor (staff surfaces treat them as a member)

Part B pins the per-machine rules fixed in this audit: a lockout, booking or live session
blocks THAT machine and never its sibling; supervised use rechecks the machine; a retired
machine's time is not bookable; the minors rule and the guest machine mode apply to booking
a machine's time. Written, not run, in the audit lane (consolidation runs it).
"""

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.audit import services as audit
from apps.machines.models import CertificationType, Machine, MachineConsumablePool, MachineSession, ServiceQueue
from apps.maintenance.repairs import services_issues
from apps.operations import live
from apps.operations.live_scope import redactor_for
from tests.audit_explorer_helpers import client_for, superadmin
from tests.fixed_roles.helpers import staff_account
from tests.machines.certification_helpers import _member
from tests.maintenance.l16_helpers import in_house, switch, world
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db

PERSONAS = ("type_manager", "technician", "full_manager", "member", "guest", "minor")
DENIED = {403, 404}
# What each persona reaches on the machine-manager surfaces: laser only, both, or nothing.
REACH = {"type_manager": {"Laser A"}, "full_manager": {"Laser A", "CNC A"}, "technician": set(),
         "member": set(), "guest": set(), "minor": set()}


def _world(slug):
    w = world(slug)
    space = w.space
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"reports"})
    space.save(update_fields=["enabled_modules"])
    switch(space, on=("machines.sessions", "machines.certifications"))
    in_house(w, coverage=[{"kind": "machine_type", "machine_type": w.kind}])
    member, _ = _member(space, f"{slug}-member")
    minor, _ = _member(space, f"{slug}-minor")
    people = {
        "type_manager": staff_account(space, f"{slug}-tm", "machine_manager", machine_types=[w.kind]),
        "full_manager": staff_account(space, f"{slug}-fm", "machine_manager", machine_types=[w.kind, w.other_kind]),
        "technician": w.tech, "member": member, "minor": minor,
        "guest": make_user(f"{slug}-guest", access_status="active"),
    }
    return SimpleNamespace(**vars(w), people=people)


@pytest.fixture
def w():
    return _world("msa0120")


def _get(actor, url, **params):
    return client_for(actor).get(url, params)


# --- A. per machine type --------------------------------------------------------------------------

@pytest.mark.parametrize("who", PERSONAS)
def test_machine_list_shows_only_the_personas_machine_types(w, who):
    response = _get(w.people[who], f"/api/v1/admin/makerspace/{w.space.pk}/machines")
    if not REACH[who]:
        assert response.status_code in DENIED or not response.json()["results"]
        return
    assert response.status_code == 200
    assert {row["name"] for row in response.json()["results"]} == REACH[who]


@pytest.mark.parametrize("who", PERSONAS)
def test_machine_detail_of_the_cnc_is_reachable_only_with_cnc_scope(w, who):
    status = _get(w.people[who], f"/api/v1/admin/machines/{w.other.pk}").status_code
    assert (status == 200) is ("CNC A" in REACH[who])
    if status != 200:
        assert status in DENIED


@pytest.mark.parametrize("who", PERSONAS)
@pytest.mark.parametrize("route", ["job-settings", "session-settings"])
def test_per_type_settings_follow_type_authority(w, who, route):
    """Fixed in this audit: both per-type settings reads resolved ANY type for any machine manager."""
    laser = _get(w.people[who], f"/api/v1/admin/makerspaces/{w.space.pk}/machine-types/{w.kind.pk}/{route}")
    cnc = _get(w.people[who], f"/api/v1/admin/makerspaces/{w.space.pk}/machine-types/{w.other_kind.pk}/{route}")
    assert (laser.status_code == 200) is ("Laser A" in REACH[who])
    assert (cnc.status_code == 200) is ("CNC A" in REACH[who])
    assert {laser.status_code, cnc.status_code} <= {200} | DENIED


@pytest.mark.parametrize("who", PERSONAS)
def test_queue_board_lanes_follow_the_scope(w, who):
    response = _get(w.people[who], f"/api/v1/admin/makerspaces/{w.space.pk}/machine-service/board",
                    machine_type_id=w.other_kind.pk)
    if not REACH[who]:
        assert response.status_code in DENIED
        return
    assert response.status_code == 200
    lanes = {lane["machine_name"] for lane in response.json()["lanes"]}
    assert lanes == ({"CNC A"} & REACH[who])


@pytest.mark.parametrize("who", PERSONAS)
def test_certification_coverage_report_lists_only_reachable_types(w, who):
    CertificationType.objects.create(makerspace=w.space, machine_type=w.kind, name="Laser induction", is_active=True)
    CertificationType.objects.create(makerspace=w.space, machine_type=w.other_kind, name="CNC induction", is_active=True)
    response = _get(w.people[who], f"/api/v1/admin/makerspace/{w.space.pk}/analytics/certification-coverage")
    if not REACH[who]:
        assert response.status_code in DENIED
        return
    assert response.status_code == 200
    body = json.dumps(response.json())
    assert ("Laser induction" in body) is ("Laser A" in REACH[who])
    assert ("CNC induction" in body) is ("CNC A" in REACH[who])


@pytest.mark.parametrize("who", ["type_manager", "full_manager"])
def test_audit_rows_of_a_type_bound_pool_follow_that_type(w, who):
    """Fixed in this audit: a pool bound to the CNC TYPE (no machine) read as shared stock."""
    pool = MachineConsumablePool.objects.create(makerspace=w.space, machine_type=w.other_kind, material="MDF",
                                                unit="millimeters", initial_grams=10, remaining_grams=10)
    shared = MachineConsumablePool.objects.create(makerspace=w.space, material="Tape", unit="millimeters",
                                                  initial_grams=5, remaining_grams=5)
    root = superadmin(f"msa-root-{who}")
    audit.record(root, "machine_consumable_pool.created", makerspace=w.space, target=pool)
    audit.record(root, "machine_consumable_pool.retired", makerspace=w.space, target=shared)
    # Audit readers here combine an audit-holding role, as in the journey suite.
    reader = staff_account(w.space, f"msa-audit-{who}", "inventory_manager", "machine_manager",
                           machine_types=[w.kind] if who == "type_manager" else [w.kind, w.other_kind])
    response = client_for(reader).get("/api/v1/admin/audit-logs", {"makerspace": w.space.pk})
    assert response.status_code == 200
    seen = {row["action"] for row in response.data["results"]}
    assert "machine_consumable_pool.retired" in seen  # a pool bound to neither stays shared
    assert ("machine_consumable_pool.created" in seen) is (who == "full_manager")


def _hint(kind, actor_id):
    return json.dumps({"kind": kind, "makerspace_id": 1, "target_type": "machine", "target_id": "7",
                       "actor_id": actor_id, "ts": "t"}, separators=(",", ":"))


@pytest.mark.parametrize("who", ["type_manager", "technician", "full_manager"])
def test_live_machine_and_repair_hints_carry_no_ids_for_scoped_readers(w, who):
    """Fixed in this audit: the stream redacted by area only, not by machine type or coverage."""
    channel = live.makerspace_channel(w.space.pk)
    for kind in ("machine_service.completed", "maintenance.issue_reported"):
        out = json.loads(redactor_for(w.people[who])(channel, _hint(kind, w.manager.pk)))
        assert out["kind"] == kind and out["actor_id"] is None and out["target_id"] == ""
    owner = json.loads(redactor_for(w.manager)(channel, _hint("machine_service.completed", w.people["member"].pk)))
    assert owner["target_id"] == "7"  # the Space Manager keeps the whole space


@pytest.mark.parametrize("who", ["type_manager", "technician"])
def test_service_state_never_writes_into_another_types_issue(w, who):
    """Fixed in this audit: `issue_id` was resolved space-wide, so a step landed on a CNC issue."""
    cnc_issue = services_issues.open_issue(w.manager, w.space, subject_type="machine", subject=w.other,
                                           title="Spindle noise")
    steps = cnc_issue.events.count()
    response = client_for(w.people[who]).post(f"/api/v1/admin/makerspaces/{w.space.pk}/service-state", {
        "subject_type": "machine", "subject_id": w.machine.pk, "in_service": False, "issue_id": cnc_issue.pk,
    }, format="json")
    assert response.status_code == 404
    assert cnc_issue.events.count() == steps  # no history step reached the CNC issue
    w.machine.refresh_from_db()
    assert w.machine.status != "maintenance"


# --- B. per machine -------------------------------------------------------------------------------

def _queue_world(slug, machines=2):
    from tests.machines.eta_helpers import world as eta_world
    w = eta_world(slug, machines=machines)
    ServiceQueue.objects.filter(pk=w.queue.pk).update(allocation_policy=ServiceQueue.AllocationPolicy.FIRST_IDLE)
    w.queue.refresh_from_db()
    return w


def _approved(w):
    from tests.machines.eta_helpers import approved
    return approved(w, 30, created=0)


def test_first_idle_skips_a_locked_out_machine_and_runs_on_its_sibling():
    from apps.machines import role_scope
    from apps.machines.service_workflow import start
    from apps.maintenance.models import MaintenanceSchedule
    w = _queue_world("msa-first-idle")
    switch(w.space, on=("machines.maintenance",))
    a, b = w.machines
    MaintenanceSchedule.objects.create(machine=a, description="Alignment", interval_days=30, blocks_use=True,
                                       next_due=timezone.localdate() - timedelta(days=10))
    started = start(_approved(w), w.staff, role_scope.EXEMPT)
    assert started.assigned_machine_id == b.pk  # the lockout blocks Laser A only


def test_first_idle_skips_a_machine_in_a_live_member_session():
    from apps.machines import role_scope
    from apps.machines.service_workflow import start
    w = _queue_world("msa-first-session")
    a, b = w.machines
    someone = make_user("msa-first-session-member", access_status="active")
    MachineSession.objects.create(makerspace=w.space, machine=a, machine_type=a.machine_type, member=someone,
                                  source="staff", started_at=timezone.now())
    assert start(_approved(w), w.staff, role_scope.EXEMPT).assigned_machine_id == b.pk


def test_a_job_cannot_start_on_a_machine_held_by_a_live_member_session():
    from apps.machines import role_scope
    from apps.machines.service_errors import ServiceMachineUnavailable
    from apps.machines.service_workflow import start
    w = _queue_world("msa-held")
    a, b = w.machines
    someone = make_user("msa-held-member", access_status="active")
    MachineSession.objects.create(makerspace=w.space, machine=a, machine_type=a.machine_type, member=someone,
                                  source="member_qr", started_at=timezone.now())
    row = _approved(w)
    with pytest.raises(ServiceMachineUnavailable):
        start(row, w.staff, role_scope.EXEMPT, machine_id=a.pk)
    assert start(row, w.staff, role_scope.EXEMPT, machine_id=b.pk).assigned_machine_id == b.pk


def test_supervised_session_refuses_a_machine_running_a_job_but_not_its_sibling():
    from apps.machines import role_scope, supervised
    from apps.machines.service_workflow import start
    from apps.machines.sessions_rules import SessionRefused
    w = _queue_world("msa-sup-job")
    switch(w.space, on=("machines.supervised_sessions",))
    a, b = w.machines
    start(_approved(w), w.staff, role_scope.EXEMPT, machine_id=a.pk)
    with pytest.raises(SessionRefused) as refused:
        supervised.open_session(a, w.staff)
    assert refused.value.code == "machine_in_use"
    assert supervised.open_session(b, w.staff).machine_id == b.pk


def test_supervised_use_stops_once_that_machine_goes_down():
    from apps.machines import supervised
    from apps.machines.sessions_rules import SessionRefused
    from tests.machines.test_induction_supervised_l3a import _world as l3a_world
    w = l3a_world("msa-sup-down")
    student, _ = _member(w.space, "msa-sup-down-student")
    session = supervised.open_session(w.machine, w.manager)
    supervised.add_supervisee(session, student, actor=w.manager)
    Machine.objects.filter(pk=w.machine.pk).update(status="maintenance")
    with pytest.raises(SessionRefused) as refused:
        supervised.start_use(session, student, actor=w.manager)
    assert refused.value.code == "machine_unavailable"


def _machine_time(w):
    from apps.bookings.models import BookableSpace
    switch(w.space, on=("machines.time_booking",))
    return BookableSpace.objects.create(makerspace=w.space, name="Laser A time", machine=w.machine,
                                        machine_type=w.kind, approval_mode=BookableSpace.ApprovalMode.INSTANT)


def test_a_retired_machines_time_is_not_bookable_and_its_sibling_still_is():
    from apps.bookings.exceptions import BookingInvalidTransition
    from apps.bookings.models import BookableSpace
    from apps.bookings.services_bookings import create_booking
    from tests.maintenance.l16_helpers import tomorrow
    w = world("msa-retired")
    time = _machine_time(w)
    other_time = BookableSpace.objects.create(makerspace=w.space, name="CNC A time", machine=w.other,
                                              machine_type=w.other_kind,
                                              approval_mode=BookableSpace.ApprovalMode.INSTANT)
    member, _ = _member(w.space, "msa-retired-member")
    Machine.objects.filter(pk=w.machine.pk).update(is_active=False, status="offline")
    start, end = tomorrow()
    with pytest.raises(BookingInvalidTransition):
        create_booking(time, member=member, actor=member, starts_at=start, ends_at=end)
    assert create_booking(other_time, member=member, actor=member, starts_at=start, ends_at=end).pk


def _booking_stub(member):
    starts = timezone.now() + timedelta(days=1)
    return SimpleNamespace(member=member, member_id=member.pk, starts_at=starts, ends_at=starts + timedelta(hours=1))


@__import__("pytest").mark.skip(reason="Decision 319: certification gating retired (machine access grants replace it); see tests/parity_0120/machine_access.")
@pytest.mark.django_db(transaction=True)
def test_booking_a_machines_time_runs_the_minors_rule():
    from apps.bookings.admission import _require_machine_person
    from apps.makerspaces import minors
    from apps.makerspaces.community_policy import CommunityError
    from apps.makerspaces.models import CommunityPolicy, GuardianConsent
    from tests.makerspaces.l4_helpers import features_on
    w = world("msa-minor-book")
    w.space.enabled_modules = sorted(set(w.space.enabled_modules or []) | {"membership"})
    w.space.save(update_fields=["enabled_modules"])
    features_on(w.space, "minors")
    CommunityPolicy.objects.create(makerspace=w.space, minors_admitted=True)
    minors.publish_terms(w.manager, w.space, "I consent to my child using the space.", "v1")
    child, _ = _member(w.space, "msa-minor-child")
    born = timezone.localdate().replace(year=timezone.localdate().year - 15, day=1).isoformat()
    profile = minors.record_minor(w.manager, w.space, child, date_of_birth=born)
    minors.sign_consent(w.manager, profile, "A Guardian", accepted=True, method=GuardianConsent.Method.STAFF_RECORDED)
    time = _machine_time(w)
    with pytest.raises(CommunityError) as refused:
        _require_machine_person(time, _booking_stub(child), timezone.now())
    assert refused.value.error_code == "minor_machines_not_allowed"
    CommunityPolicy.objects.filter(makerspace=w.space).update(minors_may_use_machines=True)
    _require_machine_person(time, _booking_stub(child), timezone.now())  # allowed by the policy now


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mode,code", [("none", "guest_pass_no_machines"),
                                       ("supervised", "guest_pass_supervised_only"),
                                       ("after_induction_cert", "guest_pass_machine_access_required")])
def test_booking_a_machines_time_runs_the_guest_machine_mode(mode, code):
    from apps.bookings.admission import _require_machine_person
    from apps.bookings.models import BookableSpace
    from apps.machines.guest_access import GuestMachineRefused
    from apps.machines.models import MachineType
    from tests.machines.test_guest_machine_modes_223 import _guest
    from tests.makerspaces.test_guest_passes import _space
    space = _space(f"msa-guest-{mode.replace('_', '-')}")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"machines", "bookings"})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"machines.time_booking"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    kind = MachineType.objects.create(makerspace=space, name="Laser", slug=f"laser-{mode}")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="Laser A")
    time = BookableSpace.objects.create(makerspace=space, name="Laser time", machine=machine, machine_type=kind,
                                        approval_mode=BookableSpace.ApprovalMode.INSTANT)
    guest, _row = _guest(space, f"msa-guest-{mode}", mode)
    stub = _booking_stub(guest)
    stub.starts_at = timezone.now() + timedelta(minutes=5)  # inside the pass window
    with pytest.raises(GuestMachineRefused) as refused:
        _require_machine_person(time, stub, timezone.now())
    assert refused.value.code == code
