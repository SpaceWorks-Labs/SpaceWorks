"""Transaction-safe module disable guard (plan A8).

The boundary `require_module` reads an unlocked row, so on its own it loses a race
against a concurrent uninstall. The creation services take the same makerspace row
lock `module_install` takes, which serializes creators against disablers.
"""

import threading

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import BookableSpace
from apps.bookings.services_bookings import create_booking
from apps.events import services as event_services
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_install import install_module, uninstall_module
from apps.makerspaces.guards import SurfaceOff
# event_reimbursements depends on events, so disabling events removes it first.
from tests.module_helpers import disable_module

pytestmark = pytest.mark.django_db(transaction=True)


def space(slug, *modules):
    item = Makerspace.objects.create(name=slug.title(), slug=slug)
    for key in modules:
        install_module(item, key)
    item.refresh_from_db()
    return item


def staff(name):
    return User.objects.create_user(username=name, email=f"{name}@example.test", password="password")


def test_creation_services_reject_a_module_disabled_after_the_boundary_check():
    # Simulates the exact race: the view-level gate passed, then the module was
    # uninstalled before the service ran.
    makerspace = space("race-events", "events")
    actor = staff("race-actor")
    disable_module(makerspace, "events")

    with pytest.raises(SurfaceOff) as exc:
        event_services.create_event(
            makerspace=makerspace, actor=actor, title="Late", description="",
            starts_at=timezone.now() + timezone.timedelta(days=1),
            ends_at=timezone.now() + timezone.timedelta(days=1, hours=2),
            location="Lab", capacity=0, is_public=True,
        )
    assert exc.value.status_code == 404 and exc.value.detail["code"] == "module_disabled"


def test_booking_creation_rejects_a_disabled_module():
    makerspace = space("race-bookings", "bookings")
    bookable = BookableSpace.objects.create(makerspace=makerspace, name="Bench")
    uninstall_module(makerspace, "bookings")

    with pytest.raises(SurfaceOff) as exc:
        create_booking(
            bookable,
            starts_at=timezone.now() + timezone.timedelta(days=1),
            ends_at=timezone.now() + timezone.timedelta(days=1, hours=1),
            name="Someone", email="someone@example.test", phone="+10000000000",
        )
    assert exc.value.status_code == 404 and exc.value.detail["code"] == "module_disabled"


def test_guard_blocks_until_a_concurrent_uninstall_commits():
    """A creator must wait for the actual uninstall lock, then observe module-off."""
    makerspace = space("race-lock", "events")
    holder_locked = threading.Event()
    release_holder = threading.Event()
    guard_started = threading.Event()
    guard_finished = threading.Event()
    guard_result, worker_errors = {}, {}

    def uninstall_holding_the_lock():
        try:
            with transaction.atomic():
                disable_module(makerspace, "events")
                holder_locked.set()  # The service has acquired and still holds the row lock.
                if not release_holder.wait(timeout=10):
                    raise TimeoutError("Test did not release the uninstall holder")
        except Exception as exc:
            worker_errors["holder"] = exc
        finally:
            connection.close()

    def run_guard():
        try:
            with transaction.atomic():
                guard_started.set()
                require_module_locked(makerspace, "events")
            guard_result["outcome"] = "allowed"
        except SurfaceOff:
            guard_result["outcome"] = "blocked"
        except Exception as exc:
            worker_errors["guard"] = exc
        finally:
            guard_finished.set()
            connection.close()

    holder = threading.Thread(target=uninstall_holding_the_lock)
    guard = threading.Thread(target=run_guard)
    holder.start()
    try:
        assert holder_locked.wait(timeout=10), worker_errors
        assert not worker_errors
        guard.start()
        assert guard_started.wait(timeout=5), worker_errors
        # An unlocked read would finish against the pre-uninstall committed row.
        assert not guard_finished.wait(timeout=0.2), (guard_result, worker_errors)
    finally:
        release_holder.set()
        holder.join(timeout=10)
        if guard.ident is not None:
            guard.join(timeout=10)
    assert not holder.is_alive() and not guard.is_alive()
    assert not worker_errors
    assert guard_result.get("outcome") == "blocked"


def test_machine_creation_still_succeeds_with_the_locked_guard_in_place():
    # Machine create is the one guarded path that runs in a view rather than a
    # service, so the added row lock sits next to `check_quota` in the same atomic
    # block. The race itself is unobservable from the outside (the boundary check
    # rejects first), but breaking the happy path would be very observable.
    from django.urls import reverse

    from apps.machines.models import Machine, MachineType
    from tests.return_helpers import authenticated_client, make_member

    makerspace = space("race-machine-create", "machines")
    manager = make_member("race-machine-manager", makerspace)
    # A per-space custom type, not the seeded global one: these tests run with
    # `transaction=True`, which truncates the migration-seeded rows.
    machine_type = MachineType.objects.create(
        makerspace=makerspace, slug="laser", name="Laser Cutter"
    )

    response = authenticated_client(manager).post(
        reverse("admin-machines", kwargs={"makerspace_id": makerspace.id}),
        {"machine_type_id": machine_type.id, "name": "Workshop Printer"},
        format="json",
    )

    assert response.status_code == 201, response.data
    assert Machine.objects.filter(makerspace=makerspace, name="Workshop Printer").exists()


def test_guard_requires_an_open_transaction_to_be_meaningful():
    # select_for_update outside atomic() raises rather than silently not locking --
    # a guard that quietly stopped locking would be worse than no guard.
    from django.db.transaction import TransactionManagementError

    makerspace = space("race-atomic", "events")
    with pytest.raises(TransactionManagementError):
        require_module_locked(makerspace, "events")
