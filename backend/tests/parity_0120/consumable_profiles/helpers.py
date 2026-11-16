"""Worlds for the consumable-profile and machine-type-template suites (decisions 341/343)."""
from decimal import Decimal
from uuid import uuid4

from apps.machines import consumable_profile_services as profiles, role_scope
from apps.machines.models import MachineConsumablePool
from apps.machines.service_workflow import accept, start
from tests.machines.certification_helpers import _manager
from tests.machines.eta_helpers import job, owner, world as eta_world
from tests.return_helpers import authenticated_client

D = Decimal


def world(slug="cp", **kwargs):
    """A tenant-local "Laser cutter" type with a pooled queue, two machines and a Space Manager (`staff`)."""
    return eta_world(f"{slug}-{uuid4().hex[:4]}", **kwargs)


def pool(w, *, unit="count", initial="10", low=None, material="Plywood"):
    return MachineConsumablePool.objects.create(
        makerspace=w.space, material=material, unit=unit, initial_grams=D(initial), remaining_grams=D(initial),
        low_threshold_grams=None if low is None else D(low))


def define(w, key="sheet", **data):
    body = {"key": key, "name": key.replace("_", " ").title(), "kind": "material", "unit": "sheet",
            "record_by": ["staff", "member", "adapter"], **data}
    return profiles.create(w.staff, w.space, w.kind, body)


def manager(w, machine_type=None):
    return _manager(w.space, f"mm-{uuid4().hex[:6]}", machine_type)[0]


def running_job(w, *, member=None, machine=0):
    member = member or owner(f"{w.space.slug}-m")
    row = job(w, member=member)
    accept(row, w.staff, estimated_minutes=10)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[machine].pk)
    row.refresh_from_db()
    return row, member


def report_dicts(key, space_id, **kwargs):
    """`report_rows` returns an export matrix (header row first); read it back as one dict per record."""
    from apps.operations.reports import report_rows
    header, *records = report_rows(key, space_id, **kwargs)
    return [dict(zip(header, record)) for record in records]


def client(user):
    return authenticated_client(user)
