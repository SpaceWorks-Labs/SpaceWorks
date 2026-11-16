"""Kit previews pin physical component content; historical evidence reads stay available."""
import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.boxes.models import QrCode
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from tests.hardware_requests.handout_support_cx11b_g4 import handout_world
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider, send
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_inventory]
COMPONENT = "e5ebda75-bc1e-4205-9d75-285dc613cd61"


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,key", [(name, key) for name in ("hardware_requests:staff-kit-preview", "hardware_requests:public-tool-checklist")
    for key in ("inventory.self_checkout", "loans.enabled", "loans.kit_checklist", "containers")]
    + [("hardware_requests:staff-kit-preview", "request_workflow")])
def test_preview_restores_exact_physical_component_expectations(native, name, key, monkeypatch):
    space, client, actor, product, _issue, _returned = handout_world(native, monkeypatch)
    product.kit_components = [{"key": COMPONENT, "label": "Probe clips", "quantity": 2}]
    product.save(update_fields=["kit_components"])
    qr = QrCode.objects.create(makerspace=space, target_type="product", target_id=product.pk)
    public = name == "hardware_requests:public-tool-checklist"
    url = reverse(name, kwargs={"makerspace_slug": space.slug} if public else {"makerspace_id": space.pk})
    body = {"payload": qr.payload, "phase": "issue"} if public else {"phase": "issue", "items": [{"product_id": product.pk, "quantity": 1}]}
    policy = key in {"loans.kit_checklist", "containers"}
    def check(response):
        assert response.data == {"components": [{"key": COMPONENT, "label": "Probe clips", "owner_label": product.name, "quantity": 2}]}
    def hidden(response):
        assert response.data == {"components": []}
        product.refresh_from_db()
        assert product.kit_components == [{"key": COMPONENT, "label": "Probe clips", "quantity": 2}]
    foreign = APIClient() if public else outsider(native)
    module_off = not public and key in {"loans.enabled", "request_workflow"}
    off = (200, None) if policy else (404, "module_disabled" if module_off else "feature_disabled")
    cycle(space, key, lambda: send(client, "POST", url, body), check, off=off, off_check=hidden if policy else None,
          refusal_key="request_workflow" if module_off else "inventory.self_checkout",
          foreign=lambda: send(foreign, "POST", url, body),
          foreign_pair=(lambda disabled: (404, "feature_disabled") if disabled and not policy else (401, "not_authenticated")) if public else (404, "not_found"), foreign_native=native and not public)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["request_workflow", "loans.enabled"])
@pytest.mark.parametrize("name", ["hardware_requests:request-timeline", "hardware_requests:admin-inventory-chain-of-custody"])
def test_historical_timeline_keeps_its_seeded_event_when_new_lending_is_off(native, key, name):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    product = make_product(space)
    row = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
        status="accepted", accepted_by=actor, accepted_at=timezone.now())
    item = HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=2, accepted_quantity=2)
    url = reverse(name, kwargs={"pk": row.pk if name == "hardware_requests:request-timeline" else product.pk})
    def check(response):
        if name == "hardware_requests:request-timeline":
            assert response.data["request_id"] == row.pk
            assert [e["kind"] for e in response.data["events"]] == ["request_accepted", "request_submitted"]
        else:
            assert (response.data["product_id"], response.data["product_name"]) == (product.pk, product.name)
            event = response.data["events"][0]
            assert (event["kind"], event["detail"]["request_item_id"], event["detail"]["accepted_quantity"]) == ("request_accepted", item.pk, 2)
    foreign = outsider(native)
    # Retained traceability reads have no lending-switch gate. Scoped private subjects
    # still require object standing in all three states (520).
    cycle(space, key, lambda: client.get(url), check, off=(200, None), off_check=check,
          foreign=lambda: foreign.get(url), foreign_native=native)
