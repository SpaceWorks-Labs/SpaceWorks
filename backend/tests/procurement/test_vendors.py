"""Vendor records (machines D12 = inventory D12): add, edit, archive, link to warranties."""

import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership
from apps.procurement.models import Vendor
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db


def space_with(slug, features=("inventory.tobuy", "inventory.vendors")):
    space = make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features or []) | set(features))
    space.save(update_fields=["enabled_features"])
    return space


def test_inventory_manager_adds_edits_and_archives_vendors():
    space = space_with("vendors-crud")
    manager = make_member("vendors-crud-im", space, MakerspaceMembership.Role.INVENTORY_MANAGER)
    client = authenticated_client(manager)
    base = f"/api/v1/procurement/makerspace/{space.pk}/vendors"
    created = client.post(base, {"name": "Parts Ltd", "email": "sales@parts.example", "phone": "+1 555"},
                          format="json")
    assert created.status_code == 201, created.content
    vendor_id = created.json()["id"]
    assert client.post(base, {"name": "parts ltd"}, format="json").status_code == 400
    edited = client.patch(f"{base}/{vendor_id}", {"website": "https://parts.example"}, format="json")
    assert edited.status_code == 200
    archived = client.patch(f"{base}/{vendor_id}", {"is_archived": True}, format="json")
    assert archived.json()["is_archived"] is True
    assert client.get(base).json() == []
    assert len(client.get(base, {"archived": "1"}).json()) == 1
    actions = list(AuditLog.objects.filter(target_id=str(vendor_id)).values_list("action", flat=True))
    assert sorted(actions) == ["vendor.archived", "vendor.created", "vendor.updated"]
    # Archived names may be reused.
    assert client.post(base, {"name": "Parts Ltd"}, format="json").status_code == 201


def test_vendors_are_tenant_scoped_and_staff_only():
    space = space_with("vendors-scope")
    other = space_with("vendors-other")
    Vendor.objects.create(makerspace=other, name="Elsewhere")
    manager = make_member("vendors-scope-sm", space)
    assert authenticated_client(manager).get(f"/api/v1/procurement/makerspace/{other.pk}/vendors").status_code == 404
    member = make_user("vendors-scope-member", access_status="active")
    response = authenticated_client(member).get(f"/api/v1/procurement/makerspace/{space.pk}/vendors")
    assert response.status_code in (403, 404)


def test_warranty_links_a_vendor_of_the_same_space_only():
    from apps.machines.models import Machine, MachineType
    from apps.warranty.services import upsert_warranty
    from rest_framework.exceptions import ValidationError
    space = space_with("vendors-warranty", ("inventory.tobuy", "inventory.vendors", "machines.warranty"))
    other = space_with("vendors-warranty-other")
    manager = make_member("vendors-warranty-sm", space)
    machine = Machine.objects.create(makerspace=space, machine_type=MachineType.objects.filter(
        makerspace__isnull=True).first(), name="Lathe")
    mine = Vendor.objects.create(makerspace=space, name="Lathe Co")
    theirs = Vendor.objects.create(makerspace=other, name="Not ours")
    warranty, _ = upsert_warranty(manager, data={"vendor_id": mine.pk}, machine=machine)
    assert warranty.vendor_id == mine.pk
    with pytest.raises(ValidationError):
        upsert_warranty(manager, data={"vendor_id": theirs.pk}, machine=machine)
