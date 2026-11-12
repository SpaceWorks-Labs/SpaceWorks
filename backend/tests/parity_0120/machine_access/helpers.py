"""Worlds for the machine access suites (decision 319): the real default, a grant is required."""
from types import SimpleNamespace
from uuid import uuid4

from apps.machines.models import Machine, MachineType
from tests.machines.certification_helpers import _manager, _member, _space
from tests.return_helpers import make_member


def world(slug="acc"):
    space = _space(f"{slug}-{uuid4().hex[:6]}", certifications=False)
    kind = MachineType.objects.create(makerspace=space, slug=f"{slug}-{uuid4().hex[:6]}", name="Laser")
    other = MachineType.objects.create(makerspace=space, slug=f"{slug}-o-{uuid4().hex[:6]}", name="Mill")
    laser = Machine.objects.create(makerspace=space, machine_type=kind, name="Laser 1")
    laser2 = Machine.objects.create(makerspace=space, machine_type=kind, name="Laser 2")
    mill = Machine.objects.create(makerspace=space, machine_type=other, name="Mill 1")
    member, membership = _member(space, f"m-{uuid4().hex[:6]}")
    boss = make_member(f"boss-{uuid4().hex[:6]}", space)
    return SimpleNamespace(space=space, kind=kind, other=other, laser=laser, laser2=laser2, mill=mill,
                           member=member, membership=membership, boss=boss)


def machine_manager(w, machine_type=None):
    return _manager(w.space, f"mm-{uuid4().hex[:6]}", machine_type)[0]
