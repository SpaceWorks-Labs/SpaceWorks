"""Public account request submission and the contextual event-registration caller."""
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.events.models import EventRegistration
from apps.hardware_requests.models import HardwareRequest
from apps.inventory.models_equipment_proposals import EquipmentProposalReceipt
from tests.accounts.account_factories import make_membership
from tests.encryption.conftest import enabled_encryption
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider, send
from tests.return_helpers import make_product

from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_lending,
              pytest.mark.usefixtures("cx11b_isolated_phase")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,key", [("hardware_requests:request-submit", "request_workflow"), ("hardware_requests:request-submit", "loans.enabled"),
    ("hardware_requests:contextual-request-self", "public_inventory"), ("hardware_requests:contextual-request-self", "loans.enabled"),
    ("hardware_requests:contextual-request-self", "events"), ("hardware_requests:contextual-request-staff", "events"),
    ("hardware_requests:contextual-request-staff", "loans.enabled")])
@enabled_encryption()
def test_request_creation_has_a_real_pending_row_items_and_receipt(native, name, key):
    space, client, objects = object_world(native)
    from apps.encryption.services import get_or_create_active_dek
    get_or_create_active_dek(space.pk)
    actor = User.objects.get(username="sx-real-object-manager")
    make_membership(actor, space)
    # The ordinary account-only path needs neither membership presence nor a member term.
    space.enabled_modules = [key for key in space.enabled_modules if key != "membership"]
    space.public_site_enabled = space.public_inventory_enabled = True
    space.save(update_fields=["enabled_modules", "public_site_enabled", "public_inventory_enabled"])
    product = make_product(space)
    registration = EventRegistration.objects.create(event=objects["event"], member=actor,
        name="Retained attendee", email=actor.email, status="registered")
    body = {"items": [{"product_id": product.pk, "quantity": 2}], "requested_for": "Workshop tools"}
    if name != "hardware_requests:request-submit":
        body.update(operation_id=str(uuid4()), event_registration_id=registration.pk)
    kwargs = {"makerspace_id": space.pk} if name.endswith("staff") else {"makerspace_slug": space.slug}
    url = reverse(name, kwargs=kwargs)

    def check(response):
        row = HardwareRequest.objects.get(makerspace=space)
        assert (row.requester_id, row.status, row.requested_for) == (actor.pk, "pending_approval", "Workshop tools")
        item = row.items.get()
        assert (item.product_id, item.requested_quantity, item.accepted_quantity, item.issued_quantity) == (product.pk, 2, 0, 0)
        product.refresh_from_db()
        assert (product.available_quantity, product.reserved_quantity) == (10, 0)
        if name != "hardware_requests:request-submit":
            receipt = EquipmentProposalReceipt.objects.get(makerspace=space)
            assert (receipt.request_id, receipt.borrower_id, receipt.creator_id) == (row.pk, actor.pk, actor.pk)
            assert response.data["replayed"] is False
    foreign = outsider(native) if name.endswith("staff") else APIClient()
    # Anonymous account-request callers retain authentication refusal; staff contextual
    # callers with no target-space standing use 481/494.
    pair = (404, "not_found") if name.endswith("staff") else (401, "not_authenticated")
    def foreign_pair(disabled):
        if name == "hardware_requests:request-submit" and key == "loans.enabled" and disabled:
            return (404, "feature_disabled")
        return pair
    # 254: the inventory master makes its modules unavailable before their
    # child gates. Staff contextual lookup also conceals an unavailable event (520).
    refusal_key = key
    off = (404, "feature_disabled" if key == "loans.enabled" else "module_disabled")
    if name != "hardware_requests:request-submit" and key == "loans.enabled":
        refusal_key = "request_workflow" if name.endswith("staff") else "public_inventory"
        off = (404, "module_disabled")
    elif name.endswith("staff") and key == "events":
        off = (404, "not_found")
    cycle(space, key, lambda: send(client, "POST", url, body), check, on=(201, None),
          off=off, refusal_key=refusal_key,
          foreign=lambda: send(foreign, "POST", url, body), foreign_pair=foreign_pair,
          audit=("request.submitted",) if name == "hardware_requests:request-submit" else ("request.submitted", "equipment.context_linked"),
          foreign_native=native and name.endswith("staff"))
