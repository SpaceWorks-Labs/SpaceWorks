"""Decision 216: workshop machine repair conflicts and event equipment warnings are read-only flags.

A machine taken for repair after its time was linked to an event shows a `machine_under_repair`
conflict on the workshop list (nothing is cancelled). The event equipment desk warns when a product
its loans use is under repair or short, reading the inventory owner's counters only.
"""
import pytest

from apps.bookings.models import Booking
from apps.events.models import Event
from apps.hardware_requests.models import HardwareRequest
from apps.inventory.models import InventoryProduct
from apps.machines.models import Machine
from tests.events.test_event_equipment_desk import _desk_setup, _link
from tests.events.test_event_workshop_machines import book, client_for, link, listing, world
from tests.test_request_workflow import authenticated_client, make_hardware_request

pytestmark = pytest.mark.django_db(transaction=True)


def test_machine_repair_after_linking_is_a_conflict_and_nothing_is_cancelled():
    maker, staff, member, event, _kinds, times = world("vc-machine")
    booking = book(times[0], member, event)
    client = client_for(staff)
    assert link(client, maker, event, booking.pk).status_code == 201
    [row] = listing(client, maker, event).data["results"]
    assert row["conflicts"] == []
    Machine.objects.filter(pk=times[0].machine_id).update(status="maintenance")
    [row] = listing(client, maker, event).data["results"]
    assert [(item["code"], item["severity"]) for item in row["conflicts"]] == [("machine_under_repair", "block")]
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.CONFIRMED
    Event.objects.filter(pk=event.pk).update(status=Event.Status.CANCELLED)
    assert listing(client, maker, event).data["results"][0]["conflicts"] == []


def _warnings(data, url):
    return authenticated_client(data.actor).get(url).data["summary"]["equipment_warnings"]


def test_desk_has_no_warnings_when_stock_is_healthy():
    data, _event, _other, url = _desk_setup("vc-desk-ok")
    assert _warnings(data, url) == []


def test_desk_warns_when_units_are_under_repair_without_changing_stock():
    data, _event, _other, url = _desk_setup("vc-desk-repair")
    InventoryProduct.objects.filter(pk=data.product.pk).update(needs_fix_quantity=2)
    before = InventoryProduct.objects.values("available_quantity", "reserved_quantity").get(pk=data.product.pk)
    assert {(row["product_id"], row["code"], row["count"]) for row in _warnings(data, url)} == {
        (data.product.pk, "units_under_repair", 2)}
    assert InventoryProduct.objects.values("available_quantity", "reserved_quantity").get(pk=data.product.pk) == before


def test_desk_warns_when_requests_awaiting_review_ask_for_more_than_is_available():
    data, event, _other, url = _desk_setup("vc-desk-short")
    available = InventoryProduct.objects.get(pk=data.product.pk).available_quantity
    pending = make_hardware_request(data.space, data.product, quantity=available + 1,
                                    status=HardwareRequest.Status.PENDING_APPROVAL)
    _link(data.space, pending, event)
    codes = {(row["code"], row["count"]) for row in _warnings(data, url)}
    assert ("insufficient_stock", available + 1) in codes
