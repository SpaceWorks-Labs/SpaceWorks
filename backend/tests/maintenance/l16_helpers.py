"""Fixtures for lane L16 (technicians, issues, repairs, item/room maintenance). Local only."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from django.utils import timezone

from apps.bookings.models import BookableSpace
from apps.machines.models import Machine, MachineType
from apps.maintenance.models import TechnicianContact, TechnicianCoverage
from tests.return_helpers import make_issued_request, make_member, make_product, make_space

REPAIRS = ("machines.repairs", "machines.maintenance", "machines.issue_reporting", "inventory.repairs",
           "inventory.maintenance", "inventory.issue_reporting", "bookings.room_repairs",
           "bookings.room_maintenance", "bookings.issue_reporting", "inventory.tobuy", "machines.tobuy")


def switch(space, *, on=(), off=()):
    space.enabled_features = sorted((set(space.enabled_features or []) | set(on)) - set(off))
    space.save(update_fields=["enabled_features"])
    return space


def world(slug, *, features=REPAIRS):
    space = make_space(f"{slug}-{uuid4().hex[:6]}")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"machines", "machine_service", "bookings"})
    space.save(update_fields=["enabled_modules"])
    switch(space, on=features)
    kind = MachineType.objects.create(makerspace=space, slug=f"laser-{uuid4().hex[:6]}", name="Laser")
    other_kind = MachineType.objects.create(makerspace=space, slug=f"cnc-{uuid4().hex[:6]}", name="CNC")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="Laser A")
    other = Machine.objects.create(makerspace=space, machine_type=other_kind, name="CNC A")
    product = make_product(space, name="Soldering iron", total_quantity=5, available_quantity=5)
    room = BookableSpace.objects.create(makerspace=space, name="Wood shop",
                                        approval_mode=BookableSpace.ApprovalMode.INSTANT)
    manager = make_member(f"{slug}-sm-{uuid4().hex[:6]}", space)
    tech = make_member(f"{slug}-tech-{uuid4().hex[:6]}", space, membership_role="technician")
    inventory_manager = make_member(f"{slug}-im-{uuid4().hex[:6]}", space, membership_role="inventory_manager")
    return SimpleNamespace(space=space, kind=kind, other_kind=other_kind, machine=machine, other=other,
                           product=product, room=room, manager=manager, tech=tech, im=inventory_manager)


def loan(w, product=None):
    request = make_issued_request(w.space, w.manager, [(product or w.product, 1)])
    return request, request.requester


def in_house(w, user=None, *, coverage=()):
    contact = TechnicianContact.objects.create(makerspace=w.space, kind="in_house", person=user or w.tech,
                                               name="Tess Tech", email="tess@example.test")
    for row in coverage:
        TechnicianCoverage.objects.create(contact=contact, **row)
    return contact


def external(w, **fields):
    return TechnicianContact.objects.create(makerspace=w.space, kind="external", name="Ravi Repairs",
                                            email="ravi@example.test", phone="+919800000000", **fields)


def tomorrow(hours=1):
    start = timezone.now() + timedelta(days=1)
    return start, start + timedelta(hours=hours)
