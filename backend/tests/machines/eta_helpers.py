"""Shared fixtures for the machine-service ETA / notices / cancellation suites."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from uuid import uuid4

from django.db import close_old_connections, transaction

from apps.machines import role_scope
from apps.machines.models import Machine, MachineServiceRequest, MachineType, ServiceQueue
from apps.machines.service_workflow import accept, start, submit
from tests.return_helpers import make_member, make_space, make_user

NOW = datetime(2026, 10, 18, 10, 0, tzinfo=dt_timezone.utc)


def at(minutes):
    return NOW + timedelta(minutes=minutes)


def enable(space, *modules, off=()):
    space.enabled_modules = sorted((set(space.enabled_modules or []) | {"machines", "machine_service", *modules}) - set(off))
    space.save(update_fields=["enabled_modules"])
    return space


def owner(username):
    user = make_user(f"{username}-{uuid4().hex[:6]}", access_status="active")
    return user


def world(slug, *, machines=2, type_name="Laser cutter", capacity=None, printing=False, membership=False):
    """A pooled queue of one tenant-local machine type with `machines` idle machines."""
    space = make_space(f"{slug}-{uuid4().hex[:6]}")
    off = (() if membership else ("membership",)) + (() if printing else ("printing",))
    enable(space, *(["printing"] if printing else []), off=off)
    if printing:
        kind = MachineType.objects.get(makerspace=None, slug="3d_printer")
    else:
        kind = MachineType.objects.create(makerspace=space, slug=f"{slug}-{uuid4().hex[:6]}", name=type_name)
    rows = [Machine.objects.create(makerspace=space, machine_type=kind, name=f"{type_name} {chr(65 + i)}") for i in range(machines)]
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=kind, name=f"{type_name} queue", capacity=capacity)
    staff = make_member(f"{slug}-staff-{uuid4().hex[:6]}", space)
    return SimpleNamespace(space=space, kind=kind, machines=rows, queue=queue, staff=staff)


def job(w, title="Job", *, member=None, target=None):
    member = member or owner(f"{w.space.slug}-owner")
    return submit(target or w.queue, member, member=member, actor=member, requester_name="Owner",
                  contact_email=member.email, contact_phone="", title=title)


def approved(w, minutes, *, created, member=None, title="Approved", target=None):
    row = job(w, title, member=member, target=target)
    accept(row, w.staff, estimated_minutes=minutes)
    MachineServiceRequest.objects.filter(pk=row.pk).update(created_at=at(created))
    row.refresh_from_db()
    return row


def pending(w, minutes=0, *, created, member=None, title="Pending", target=None):
    row = job(w, title, member=member, target=target)
    MachineServiceRequest.objects.filter(pk=row.pk).update(created_at=at(created), estimated_minutes=minutes)
    row.refresh_from_db()
    return row


def running(w, machine, minutes, *, started_ago, created=-120, member=None, title="Running"):
    row = approved(w, minutes, created=created, member=member, title=title)
    start(row, w.staff, role_scope.EXEMPT, machine_id=machine.pk, estimated_minutes=minutes)
    MachineServiceRequest.objects.filter(pk=row.pk).update(started_at=at(-started_ago))
    row.refresh_from_db()
    return row


def owner_fixture(w):
    """Owner multi-printer regression made concrete at 10:00 UTC (decision 44)."""
    a, b = w.machines
    run_a = running(w, a, 20, started_ago=10, title="Running A")   # 10 min left
    run_b = running(w, b, 40, started_ago=10, title="Running B")   # 30 min left
    first = approved(w, 60, created=-50, title="Predecessor 1")
    second = approved(w, 20, created=-40, title="Predecessor 2")
    target = approved(w, 15, created=-30, title="Target")
    return SimpleNamespace(run_a=run_a, run_b=run_b, first=first, second=second, target=target)


def interleave(first, second, *, pause=0.4):
    """Run ``first`` holding its locks inside an open transaction, then ``second`` on
    another connection; release ``first`` after ``pause``. Returns both outcomes
    (a value or the raised exception) so callers can assert no deadlock either way."""
    started, release, results = threading.Event(), threading.Event(), {}

    def run_first():
        close_old_connections()
        try:
            with transaction.atomic():
                results["first"] = first()
                started.set()
                release.wait(15)
        except Exception as exc:  # noqa: BLE001 - the outcome is the assertion subject
            results["first"] = exc
        finally:
            started.set()
            close_old_connections()

    def run_second():
        close_old_connections()
        started.wait(15)
        try:
            results["second"] = second()
        except Exception as exc:  # noqa: BLE001
            results["second"] = exc
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = pool.submit(run_first), pool.submit(run_second)
        started.wait(15)
        time.sleep(pause)
        release.set()
        one.result(60)
        two.result(60)
    return results.get("first"), results.get("second")


def is_deadlock(outcome):
    return isinstance(outcome, Exception) and "deadlock" in str(outcome).lower()
