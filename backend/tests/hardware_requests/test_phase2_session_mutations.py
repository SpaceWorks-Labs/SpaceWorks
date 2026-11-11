"""Equipment session mutations: real request fixtures, unrun source."""
from uuid import uuid4
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models import Event, EventRegistration
from apps.inventory.models_equipment_proposals import (
    EquipmentKitTemplate, EquipmentKitVersion, EquipmentProposalReceipt,
)
from tests.bookings.admin_api_helpers import grant
from tests.encryption.conftest import enabled_encryption
from tests.test_request_workflow import authenticated_client, make_member, make_product, make_space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("operation", ["create", "version", "publication", "archive"])
def test_kit_mutation_accepts_matching_origin_and_refuses_other_origin(operation):
    own, other = make_space("kit-own-" + operation), make_space("kit-other-" + operation)
    for maker in (own, other):
        maker.frontend_domain = maker.slug + ".example.test"
        maker.frontend_domain_status = "verified"
        maker.enabled_modules = list(set(maker.enabled_modules or []) | {"staff_admin"})
        maker.save(update_fields=["frontend_domain", "frontend_domain_status", "enabled_modules"])
    actor = make_member("kit-actor-" + operation, own)
    grant(actor, other)
    product = make_product(own, name="tool", is_public=True)
    line = {"product_id": product.pk, "quantity_per_person": 1, "kind": "returnable"}
    kit = EquipmentKitTemplate.objects.create(makerspace=own, name="kit", published_for_contexts=False)
    EquipmentKitVersion.objects.create(template=kit, version=1, name="kit", lines=[line])
    base = f"/api/v1/admin/makerspace/{own.pk}/equipment-kits"
    path, body = {
        "create": (base, {"name": "new kit", "lines": [line]}),
        "version": (f"{base}/{kit.pk}/versions", {"name": "new version", "lines": [line], "expected_revision": kit.revision}),
        "publication": (f"{base}/{kit.pk}/publication", {"published_for_contexts": True, "expected_revision": kit.revision}),
        "archive": (f"{base}/{kit.pk}/archive", {"archived": True, "expected_revision": kit.revision}),
    }[operation]
    client = authenticated_client(actor)
    initial = (EquipmentKitTemplate.objects.count(), EquipmentKitVersion.objects.count(), AuditLog.objects.count())
    denied = client.post(path, body, format="json", HTTP_ORIGIN=f"https://{other.frontend_domain}")
    assert denied.status_code == 403, denied.content
    assert initial == (EquipmentKitTemplate.objects.count(), EquipmentKitVersion.objects.count(), AuditLog.objects.count())
    allowed = client.post(path, body, format="json", HTTP_ORIGIN=f"https://{own.frontend_domain}")
    assert allowed.status_code == (201 if operation in {"create", "version"} else 200), allowed.content
    changed = (EquipmentKitTemplate.objects.count(), EquipmentKitVersion.objects.count(), AuditLog.objects.count())
    assert changed != initial
    if operation != "create":
        other_path = path.replace(f"/makerspace/{own.pk}/", f"/makerspace/{other.pk}/")
        denied = client.post(other_path, body, format="json", HTTP_ORIGIN=f"https://{other.frontend_domain}")
        assert denied.status_code in (403, 404), denied.content
        assert changed == (EquipmentKitTemplate.objects.count(), EquipmentKitVersion.objects.count(), AuditLog.objects.count())


def test_matching_public_kit_list_and_detail_are_scoped_to_published_tenant():
    own, other = make_space("member-kit-own"), make_space("member-kit-other")
    for maker in (own, other):
        maker.public_site_enabled = True
        maker.public_inventory_enabled = True
        maker.save(update_fields=["public_site_enabled", "public_inventory_enabled"])
    actor = make_member("member-kit-actor", own)
    from tests.payments.membership_rows import community_membership
    community_membership(own, actor)  # the public kit list needs an active membership
    product = make_product(own, name="tool", is_public=True)
    kit = EquipmentKitTemplate.objects.create(makerspace=own, name="kit", published_for_contexts=True)
    EquipmentKitVersion.objects.create(template=kit, version=1, name="kit", lines=[
        {"product_id": product.pk, "quantity_per_person": 1, "kind": "returnable"},
    ])
    client = authenticated_client(actor)
    listing = client.get(f"/api/v1/public/{own.slug}/equipment-kits/")
    assert listing.status_code == 200, listing.content
    assert [row["id"] for row in listing.data["results"]] == [kit.pk]
    detail = client.get(f"/api/v1/public/{own.slug}/equipment-kits/{kit.pk}/")
    assert detail.status_code == 200 and detail.data["id"] == kit.pk
    foreign = client.get(f"/api/v1/public/{other.slug}/equipment-kits/{kit.pk}/")
    assert foreign.status_code in (403, 404), foreign.content


@pytest.mark.parametrize("detail", [False, True])
def test_public_kit_route_remains_slug_scoped_with_another_origin(detail):
    own, other = make_space("member-origin-own-" + str(detail)), make_space("member-origin-other-" + str(detail))
    for maker in (own, other):
        maker.frontend_domain = maker.slug + ".example.test"
        maker.frontend_domain_status = "verified"
        maker.public_site_enabled = True
        maker.public_inventory_enabled = True
        maker.save(update_fields=["frontend_domain", "frontend_domain_status", "public_site_enabled", "public_inventory_enabled"])
    actor = make_member("member-origin-actor-" + str(detail), own)
    product = make_product(own, name="tool", is_public=True)
    kit = EquipmentKitTemplate.objects.create(makerspace=own, name="kit", published_for_contexts=True)
    EquipmentKitVersion.objects.create(template=kit, version=1, name="kit", lines=[
        {"product_id": product.pk, "quantity_per_person": 1, "kind": "returnable"},
    ])
    path = f"/api/v1/public/{own.slug}/equipment-kits/" + (f"{kit.pk}/" if detail else "")
    client = authenticated_client(actor)
    matching = client.get(path, HTTP_ORIGIN=f"https://{own.frontend_domain}")
    assert matching.status_code == 200, matching.content
    # Member routes use slug/account/publication gates, not the staff-origin
    # permission. CORS transport behavior is exercised separately.
    foreign_origin = client.get(path, HTTP_ORIGIN=f"https://{other.frontend_domain}")
    assert foreign_origin.status_code == 200, foreign_origin.content
    assert foreign_origin.data == matching.data


def test_linked_use_rejects_foreign_origin_without_adjustment_or_receipt():
    from apps.inventory.models_equipment_proposals import EquipmentConsumablePlan, EquipmentConsumableUseReceipt
    from apps.operations.models import InventoryAdjustment

    own, other = make_space("use-origin-own"), make_space("use-origin-other")
    for maker in (own, other):
        maker.frontend_domain = maker.slug + ".example.test"
        maker.frontend_domain_status = "verified"
        maker.enabled_modules = list(set(maker.enabled_modules or []) | {"staff_admin"})
        maker.enabled_features = list(set(maker.enabled_features or []) | {"inventory.consumables"})
        maker.save(update_fields=["frontend_domain", "frontend_domain_status", "enabled_modules", "enabled_features"])
    actor = make_member("use-origin-actor", own)
    grant(actor, other)
    product = make_product(own, name="supply", is_public=True, is_consumable=True, total_quantity=10, available_quantity=10)
    lines = [{"product_id": product.pk, "quantity_per_person": 1, "kind": "consumable"}]
    template = EquipmentKitTemplate.objects.create(makerspace=own, name="supply kit", published_for_contexts=True)
    version = EquipmentKitVersion.objects.create(template=template, version=1, name="supply kit", lines=lines)
    plan = EquipmentConsumablePlan.objects.create(makerspace=own, borrower=actor, kit_version=version, lines=lines)
    path = f"/api/v1/admin/makerspace/{own.pk}/consumables/{product.pk}/use"
    body = {"operation_id": str(uuid4()), "quantity": 1, "note": "", "allocation_id": None, "plan_id": plan.pk}
    client = authenticated_client(actor)
    before = (InventoryAdjustment.objects.count(), EquipmentConsumableUseReceipt.objects.count(), AuditLog.objects.count())
    with enabled_encryption():
        denied = client.post(path, body, format="json", HTTP_ORIGIN=f"https://{other.frontend_domain}")
        assert denied.status_code == 403, denied.content
        assert before == (InventoryAdjustment.objects.count(), EquipmentConsumableUseReceipt.objects.count(), AuditLog.objects.count())
        cross = client.post(path.replace(f"/makerspace/{own.pk}/", f"/makerspace/{other.pk}/"), body,
                            format="json", HTTP_ORIGIN=f"https://{other.frontend_domain}")
        assert cross.status_code in (403, 404), cross.content
        assert before == (InventoryAdjustment.objects.count(), EquipmentConsumableUseReceipt.objects.count(), AuditLog.objects.count())
        allowed = client.post(path, body, format="json", HTTP_ORIGIN=f"https://{own.frontend_domain}")
    assert allowed.status_code == 200, allowed.content
    assert allowed.data == {"status": "recorded", "replayed": False}
    assert EquipmentConsumableUseReceipt.objects.count() == before[1] + 1


def test_contextual_self_uses_member_scope_and_replays_across_origins():
    own, other = make_space("context-member-own"), make_space("context-member-other")
    for maker in (own, other):
        maker.frontend_domain = maker.slug + ".example.test"
        maker.frontend_domain_status = "verified"
        maker.public_site_enabled = True
        maker.public_inventory_enabled = True
        maker.enabled_modules = list(set(maker.enabled_modules or []) | {"public_inventory", "request_workflow"})
        maker.enabled_features = list(set(maker.enabled_features or []) | {"loans.enabled"})
        maker.save(update_fields=["frontend_domain", "frontend_domain_status", "public_site_enabled", "public_inventory_enabled", "enabled_modules", "enabled_features"])
    actor = make_member("context-member-actor", own)
    product = make_product(own, name="tool", is_public=True)
    client = authenticated_client(actor)
    path = f"/api/v1/public/{own.slug}/requests/contextual"
    body = {"operation_id": str(uuid4()), "items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "workshop"}
    before = (EquipmentProposalReceipt.objects.count(), AuditLog.objects.count())
    with enabled_encryption():
        allowed = client.post(path, body, format="json", HTTP_ORIGIN=f"https://{own.frontend_domain}")
        assert allowed.status_code == 201, allowed.content
        replay = client.post(path, body, format="json", HTTP_ORIGIN=f"https://{other.frontend_domain}")
    assert replay.status_code == 200 and replay.data["replayed"] is True, replay.content
    assert EquipmentProposalReceipt.objects.count() == before[0] + 1


def test_contextual_staff_requires_matching_origin_and_same_tenant_registration():
    own, other = make_space("context-staff-own"), make_space("context-staff-other")
    for maker in (own, other):
        maker.frontend_domain = maker.slug + ".example.test"
        maker.frontend_domain_status = "verified"
        maker.enabled_modules = list(set(maker.enabled_modules or []) | {"staff_admin", "events", "request_workflow"})
        maker.enabled_features = list(set(maker.enabled_features or []) | {"loans.enabled"})
        maker.save(update_fields=["frontend_domain", "frontend_domain_status", "enabled_modules", "enabled_features"])
    actor = make_member("context-staff-actor", own)
    grant(actor, other)
    borrower = make_member("context-staff-borrower", own)
    product = make_product(own, name="tool", is_public=True)
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=own, title="event", starts_at=start, ends_at=start + timedelta(hours=1))
    registration = EventRegistration.objects.create(event=event, member=borrower, name="Member",
        email=borrower.email, phone="12345678", status=EventRegistration.Status.REGISTERED)
    client = authenticated_client(actor)
    body = {"operation_id": str(uuid4()), "event_registration_id": registration.pk,
            "items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "workshop"}
    path = f"/api/v1/admin/makerspace/{own.pk}/equipment-requests/contextual"
    before = (EquipmentProposalReceipt.objects.count(), AuditLog.objects.count())
    with enabled_encryption():
        denied = client.post(path, body, format="json", HTTP_ORIGIN=f"https://{other.frontend_domain}")
        assert denied.status_code == 403, denied.content
        assert before == (EquipmentProposalReceipt.objects.count(), AuditLog.objects.count())
        cross = client.post(path.replace(f"/makerspace/{own.pk}/", f"/makerspace/{other.pk}/"), body,
                            format="json", HTTP_ORIGIN=f"https://{other.frontend_domain}")
        assert cross.status_code in (403, 404), cross.content
        assert before == (EquipmentProposalReceipt.objects.count(), AuditLog.objects.count())
        allowed = client.post(path, body, format="json", HTTP_ORIGIN=f"https://{own.frontend_domain}")
    assert allowed.status_code == 201, allowed.content
    assert EquipmentProposalReceipt.objects.count() == before[0] + 1
