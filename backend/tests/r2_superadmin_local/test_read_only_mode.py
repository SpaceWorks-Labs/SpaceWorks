"""#185 item 2: read-only lets everyone view and export, and refuses every create/update
across modules through the one guard; lifting restores writes."""

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.space_controls.errors import SpaceControlConflict, SpaceReadOnly
from apps.space_controls.models import SpaceControlState
from apps.space_controls.services_access import lift_read_only, set_read_only
from apps.space_controls.write_policy import enforcing_read_only, fanout_context
from apps.tenant_migration.gate_runtime import fanout_tenant_write, tenant_write

from .helpers import REASON, api, control, manager, member, space, superadmin

pytestmark = pytest.mark.django_db
SOURCE = SpaceControlState.ReadOnlySource


@pytest.fixture
def world(mailbox, django_capture_on_commit_callbacks):
    lab = space()
    root, boss, person = superadmin(), manager(lab), member(lab)
    with django_capture_on_commit_callbacks(execute=True):
        response = control(root, lab, "read-only", {"reason": REASON})
    assert response.status_code == 200 and response.json()["state"] == "read_only", response.content
    return type("World", (), dict(lab=lab, root=root, boss=boss, person=person, mail=mailbox))


# One write route per module family; the guard refuses them all before any view runs.
WRITES = [
    ("admin-staff-invitations", {"email": "new@example.test", "roles": ["inventory_manager"]}),
    ("admin-module-install", {"module": "events"}),
    ("admin-membership-invitations", {"email": "join@example.test"}),
    ("admin-member-cards", {}),
    ("admin-work-orders", {"title": "Fix the lathe"}),
    ("admin-consumables", {"name": "PLA"}),
    ("machine-materials", {"name": "Plywood"}),
    ("admin-saved-views", {"name": "Mine"}),
    ("report-schedules", {"name": "Weekly"}),
    ("admin-makerspace-waiver", {"text": "Be safe"}),
]


@pytest.mark.parametrize("name, body", WRITES)
def test_writes_are_refused_for_staff(world, name, body):
    url = reverse(name, kwargs={"makerspace_id": world.lab.pk})
    for actor in (world.boss, member(world.lab, f"{name}-member")):
        response = api(actor).post(url, body, format="json")
        assert response.status_code == 423, (name, response.status_code)
        assert response.json()["code"] == "space_read_only"


@pytest.mark.parametrize("name, body", WRITES)
def test_the_superadmin_may_write_and_every_such_write_is_audited(world, name, body):
    # #195 (#110/#190): nothing is switched off for the superadmin. A real bearer token is
    # needed: the gate recognises the superadmin before authentication and confirms after it.
    from tests.stage4.helpers import bearer_client
    url = reverse(name, kwargs={"makerspace_id": world.lab.pk})
    response = bearer_client(world.root, recent=True).post(url, body, format="json")
    assert response.status_code != 423, (name, response.status_code)
    entry = AuditLog.objects.filter(action="space_control.superadmin_bypass", makerspace=world.lab).latest("created_at")
    assert entry.actor == world.root and entry.meta["bypass_space_control"] == "read_only"
    assert entry.meta["path"] == name


def test_reads_and_exports_still_work(world):
    usage = api(world.boss).get(f"/api/v1/admin/makerspace/{world.lab.pk}/usage")
    assert usage.status_code == 200
    export = api(world.boss).post(reverse("data-export-list-create", kwargs={"makerspace_id": world.lab.pk}),
                                  {}, format="json")
    assert export.status_code != 423


def test_the_bypass_needs_a_confirmed_live_superadmin(world):
    from apps.space_controls.superadmin_bypass import Bypass, scope
    with scope(Bypass(label="unit", actor=world.root, phase="confirmed")), enforcing_read_only():
        with tenant_write(world.lab.pk):
            pass
    assert AuditLog.objects.filter(action="space_control.superadmin_bypass", actor=world.root).count() == 1
    for phase in ("dispatched", "revoked"):
        with pytest.raises(SpaceReadOnly):
            with scope(Bypass(label="unit", phase=phase)), enforcing_read_only(), tenant_write(world.lab.pk):
                pass
    from apps.space_controls.superadmin_bypass import confirm
    with pytest.raises(SpaceReadOnly):
        with scope(Bypass(label="unit")) as bypass, enforcing_read_only():
            confirm(world.boss)  # a staff actor revokes a pending bypass
            assert bypass.phase == "revoked"
            with tenant_write(world.lab.pk):
                pass


def test_jobs_queued_by_a_superadmin_keep_the_bypass(world):
    from apps.space_controls.superadmin_bypass import HEADER, Bypass, for_task, publish_headers, scope
    headers = {}
    with scope(Bypass(label="unit", actor=world.root, phase="confirmed")):
        publish_headers(headers=headers)
    assert headers == {HEADER: world.root.pk}
    request = type("Request", (), {HEADER: world.root.pk})()
    assert for_task(request, "some.task").actor == world.root
    assert for_task(type("Request", (), {HEADER: world.boss.pk})(), "some.task") is None
    assert for_task(type("Request", (), {})(), "some.task") is None


def test_the_guard_only_refuses_where_enforcement_is_on(world):
    with tenant_write(world.lab.pk):
        pass  # deliveries, tasks and maintenance create nothing new
    with pytest.raises(SpaceReadOnly):
        with enforcing_read_only(), tenant_write(world.lab.pk):
            pass
    counts = {}
    with fanout_tenant_write(world.lab.pk, operation="membership_renewal", counts=counts) as allowed:
        assert allowed is False
    with fanout_tenant_write(world.lab.pk, operation="notification_contract_outbox", counts=counts) as allowed:
        assert allowed is True
    assert counts == {"skipped": 1}
    with fanout_context("gateway_poll"), enforcing_read_only(), tenant_write(world.lab.pk):
        pass  # settlement is permitted in every state


def test_banner_carries_the_reason_and_the_manager_is_mailed(world):
    notices = api(world.person).get("/api/v1/platform-notices").json()
    assert notices["spaces"][0]["state"] == "read_only" and notices["spaces"][0]["reason"] == REASON
    assert world.mail[-1].to == [world.boss.email] and REASON in world.mail[-1].body
    assert AuditLog.objects.get(action="space_control.read_only_enabled").meta == {"source": "manual"}


def test_lift_restores_writes(world, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        assert control(world.root, world.lab, "read-only/lift").json()["state"] == "active"
    url = reverse("admin-staff-invitations", kwargs={"makerspace_id": world.lab.pk})
    response = api(world.root).post(url, {"email": "new@example.test", "roles": ["inventory_manager"]},
                                    format="json")
    assert response.status_code != 423
    with enforcing_read_only(), tenant_write(world.lab.pk):
        pass
    assert api(world.person).get("/api/v1/platform-notices").json()["spaces"] == []
    assert control(world.root, world.lab, "read-only/lift").json()["code"] == "space_not_read_only"


def test_automatic_sources_are_idempotent_and_only_lift_themselves(world):
    other = space("south-lab")
    assert set_read_only(None, other.pk, "Trial ended.", source=SOURCE.TRIAL_EXPIRED) is not None
    assert set_read_only(None, other.pk, "Trial ended.", source=SOURCE.TRIAL_EXPIRED) is None
    assert lift_read_only(None, other.pk, source=SOURCE.PAYMENT_OVERDUE) is None
    assert SpaceControlState.objects.get(makerspace=other).read_only_at is not None
    assert lift_read_only(None, other.pk, source=SOURCE.TRIAL_EXPIRED) is not None
    # A manual read-only is never lifted by an automatic source.
    assert lift_read_only(None, world.lab.pk, source=SOURCE.TRIAL_EXPIRED) is None
    with pytest.raises(SpaceControlConflict):
        set_read_only(world.root, world.lab.pk, REASON)
