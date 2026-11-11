"""Session origin and tenant isolation: private source candidate, unrun."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models import BookableSpace
from apps.events.models import Event
from apps.inventory.models_equipment_proposals import (
    EquipmentConsumableUseReceipt, EquipmentKitTemplate, EquipmentKitVersion,
    EquipmentProposalReceipt,
)
from tests.bookings.admin_api_helpers import grant
from tests.test_request_workflow import authenticated_client, make_member, make_product, make_space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("kind", ["kits", "kit", "event_products", "event_kits", "space_products", "space_kits", "sources"])
def test_scoped_reads_require_matching_origin_and_reject_foreign_resource(kind):
    own, other = make_space("session-own-" + kind), make_space("session-other-" + kind)
    for maker in (own, other):
        maker.frontend_domain = maker.slug + ".example.test"
        maker.frontend_domain_status = "verified"
        maker.enabled_modules = list(set(maker.enabled_modules or []) | {"staff_admin", "events", "bookings", "request_workflow"})
        maker.enabled_features = list(set(maker.enabled_features or []) | {"loans.enabled", "inventory.consumables"})
        maker.save(update_fields=["frontend_domain", "frontend_domain_status", "enabled_modules", "enabled_features"])
    actor = make_member("session-actor-" + kind, own)
    grant(actor, other)
    tool = make_product(own, name="tool", is_public=True)
    supply = make_product(own, name="supply", is_public=True, is_consumable=True)
    kit = EquipmentKitTemplate.objects.create(makerspace=own, name="kit", published_for_contexts=True)
    EquipmentKitVersion.objects.create(template=kit, version=1, name="kit", lines=[{"product_id": tool.pk, "quantity_per_person": 1, "kind": "returnable"}])
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=own, title="event", starts_at=start, ends_at=start + timedelta(hours=1))
    room = BookableSpace.objects.create(makerspace=own, name="room")
    paths = {"kits": "equipment-kits", "kit": f"equipment-kits/{kit.pk}", "event_products": f"events/{event.pk}/equipment-request-products",
             "event_kits": f"events/{event.pk}/equipment-kits", "space_products": f"spaces/{room.pk}/equipment-request-products",
             "space_kits": f"spaces/{room.pk}/equipment-kits", "sources": f"consumables/{supply.pk}/equipment-sources"}
    client = authenticated_client(actor)
    url = f"/api/v1/admin/makerspace/{own.pk}/{paths[kind]}"
    before = (EquipmentKitTemplate.objects.count(), EquipmentKitVersion.objects.count(),
              EquipmentProposalReceipt.objects.count(), EquipmentConsumableUseReceipt.objects.count())
    response = client.get(url, HTTP_ORIGIN=f"https://{own.frontend_domain}")
    assert response.status_code == 200, response.content
    response = client.get(url, HTTP_ORIGIN=f"https://{other.frontend_domain}")
    assert response.status_code == 403, response.content
    if kind != "kits":
        other_url = f"/api/v1/admin/makerspace/{other.pk}/{paths[kind]}"
        response = client.get(other_url, HTTP_ORIGIN=f"https://{other.frontend_domain}")
        assert response.status_code in (403, 404), response.content
    assert before == (EquipmentKitTemplate.objects.count(), EquipmentKitVersion.objects.count(),
                      EquipmentProposalReceipt.objects.count(), EquipmentConsumableUseReceipt.objects.count())
