import json
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command

from apps.boxes.models import QrCode
from apps.hardware_requests.models import HardwareRequest
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceWaiver
from apps.machines.models import Machine, MachineType, ServiceQueue, MakerspaceMachineTypePricing
from apps.machines.models_policy import MakerspaceMachineTypePolicy
from apps.machines.job_intake import job_queues, require_member_job_gate
from apps.machines.public_intake_access import require_public_machine_requester
from apps.makerspaces.waiver_state import current_acceptance
from apps.operations.management.commands._seed_e2e_discovery import seed_machine_journey
from apps.payments.pricing import quote
from apps.presence.models import PresenceSession

pytestmark = pytest.mark.django_db


def test_seed_e2e_creates_a_fresh_makerspace_with_both_requests(settings, tmp_path, monkeypatch):
    settings.DEBUG = True
    settings.EVENT_STATION_PIN_PEPPER = "test-only-independent-station-pepper"
    monkeypatch.delenv("E2E_SEED_ALLOWED", raising=False)
    out = tmp_path / "seed.json"
    call_command("seed_e2e", "--write-json", str(out), "--password", "pw-for-test")
    seeded = json.loads(out.read_text())
    space = Makerspace.objects.get(slug=seeded["slug"])
    assert space.public_inventory_enabled
    assert space.products.filter(name=seeded["product"], storage_location=seeded["secret_location"]).exists()
    pending = HardwareRequest.objects.get(pk=seeded["pending_request_id"])
    probe = HardwareRequest.objects.get(pk=seeded["probe_request_id"])
    assert pending.requester.account_kind == "member"
    manager = User.objects.get(username=seeded["manager"]["username"])
    # Decision 63: one account per person; the manager is a member-kind account holding a
    # staff-track row in the seeded space.
    assert manager.account_kind == "member"
    assert MakerspaceMembership.staff_tracks.filter(user=manager, makerspace=space).exists()
    fixture = assert_machine_journey_fixture(seeded, space)
    member = User.objects.get(username=seeded["member"]["username"])
    before = machine_fixture_snapshot(space, member)
    assert seed_machine_journey(space, manager, member) == fixture
    assert machine_fixture_snapshot(space, member) == before
    assert pending.status == HardwareRequest.Status.PENDING_APPROVAL
    assert probe.status == HardwareRequest.Status.ACCEPTED
    assert space.boxes.filter(code=seeded["box_code"]).exists()
    # The handover wizard resolves the container through its QR label, so the seeded box carries one.
    assert QrCode.objects.filter(makerspace=space, payload=seeded["box_code"], target_type=QrCode.TargetType.BOX).exists()
    # Two runs never collide: fresh slug, fresh users, fresh box code.
    out2 = tmp_path / "seed2.json"
    call_command("seed_e2e", "--write-json", str(out2), "--password", "pw-for-test")
    second = json.loads(out2.read_text())
    assert second["slug"] != seeded["slug"]
    assert second["manager"]["username"] != seeded["manager"]["username"]
    assert_machine_journey_fixture(second, Makerspace.objects.get(pk=second["makerspace_id"]))
    for key in ("queue_id", "machine_type_id", "machine_id"):
        assert second["machine_journey"][key] != fixture[key]
    assert machine_fixture_snapshot(space, member) == before


def test_seed_e2e_refuses_outside_development(settings, monkeypatch):
    settings.DEBUG = False
    settings.EVENT_STATION_PIN_PEPPER = "test-only-independent-station-pepper"
    monkeypatch.delenv("E2E_SEED_ALLOWED", raising=False)
    before = Makerspace.objects.count()
    with pytest.raises(CommandError):
        call_command("seed_e2e")
    assert Makerspace.objects.count() == before
    monkeypatch.setenv("E2E_SEED_ALLOWED", "1")
    call_command("seed_e2e", "--password", "pw-for-test")
    assert Makerspace.objects.count() == before + 1


def machine_fixture_snapshot(space, member):
    """A repeated provision or another tenant's seed must leave the first fixture intact."""
    return {
        "types": list(MachineType.objects.filter(makerspace=space).order_by("pk").values()),
        "queues": list(ServiceQueue.objects.filter(makerspace=space).order_by("pk").values()),
        "machines": list(Machine.objects.filter(makerspace=space).order_by("pk").values()),
        "policy": list(MakerspaceMachineTypePolicy.objects.filter(makerspace=space).order_by("pk").values()),
        "prices": list(MakerspaceMachineTypePricing.objects.filter(makerspace=space).order_by("pk").values()),
        "terms": list(MakerspaceMembership.objects.get(makerspace=space, user=member).terms.values_list("pk", flat=True)),
        "presence": list(PresenceSession.objects.filter(makerspace=space, member=member).values_list("pk", flat=True)),
        "waivers": list(MakerspaceWaiver.objects.filter(makerspace=space).values_list("pk", flat=True)),
    }


def assert_machine_journey_fixture(seeded, space):
    fixture = seeded["machine_journey"]
    kind = MachineType.objects.get(pk=fixture["machine_type_id"], makerspace=space)
    assert kind.capability_config == {"metering_unit": "minutes", "requires_booking": False}
    assert kind.slug == "e2e-minute-service" and kind.is_builtin is False
    queue = ServiceQueue.objects.get(pk=fixture["queue_id"], makerspace=space, machine_type=kind)
    assert queue.is_active is True
    assert [row.pk for row in job_queues(space)] == [queue.pk]
    machine = Machine.objects.get(pk=fixture["machine_id"], makerspace=space, machine_type=kind)
    assert machine.status == "idle" and machine.is_active and machine.is_public and machine.open_to_all_members
    policy = MakerspaceMachineTypePolicy.objects.get(makerspace=space, machine_type=kind)
    assert (policy.accepts_job_requests, policy.quote_mode, policy.payment_timing, policy.file_groups) == (
        True, "always", "completion", ["fab-3dprint"])
    price = MakerspaceMachineTypePricing.objects.get(makerspace=space, machine_type=kind)
    assert (price.payment_enabled, price.rate_per_unit, price.flat_fee) == (True, Decimal("2"), Decimal("5"))
    member = User.objects.get(username=seeded["member"]["username"])
    membership = MakerspaceMembership.objects.get(makerspace=space, user=member, status="active")
    active = require_public_machine_requester(member, space)
    assert active.membership.pk == membership.pk and active.session.member_id == member.pk
    assert active.session.status == "visiting" and active.session.ended_at is None
    assert current_acceptance(membership, active_waiver=active.accepted_waiver)
    assert membership.terms.filter(status="active", starts_at__lte=active.session.started_at,
                                    ends_at__gt=active.session.expires_at).count() == 1
    require_member_job_gate(space, member, kind)
    for minutes, expected in ((30, Decimal("65.00")), (20, Decimal("45.00"))):
        priced = quote(space, "machines", member=member, params={"machine": machine, "minutes": minutes})
        assert priced.total == expected and priced.currency == "usd" and priced.discount is None
    assert {"machines", "machine_service", "membership", "presence"}.issubset(space.enabled_modules)
    assert {"machines.job_requests", "machines.job_quotes", "charges.enabled", "charges.machines"}.issubset(space.enabled_features)
    assert {"payments.machines", "charges.pricing", "charges.discounts", "billing.tax"}.isdisjoint(space.enabled_features)
    return fixture
