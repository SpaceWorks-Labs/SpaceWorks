"""Procurement receipts and machine-type documents use real HTTP quota boundaries."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.machines import storage as machine_storage
from apps.machines.models import Machine, MachineDocument, MachineType
from apps.machines.models_type_setup import MachineTypeDocument
from apps.makerspaces.models import Makerspace
from apps.procurement import storage as receipt_storage
from apps.procurement.models import ToBuyItem, ToBuyReceipt
from tests.inventory.test_alternative_creators_cx7_p4a import race
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]
KEYS = [("upload_bytes", 400, "upload_limit"), ("storage", 400, "limit_reached"),
        ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached")]
KINDS = ["receipt", "type_document", "machine_document"]


def world(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-private-upload")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"machines"})
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.tobuy"})
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["enabled_modules", "enabled_features", "resource_limit_overrides"])
    sizes = {}
    monkeypatch.setattr(receipt_storage, "finalize_receipt_upload", lambda item, key:
                        SimpleNamespace(size=sizes[key], content_type="application/pdf"))
    monkeypatch.setattr(machine_storage, "finalize_upload", lambda *args: None)
    monkeypatch.setattr(machine_storage, "validate_machine_object", lambda key:
                        SimpleNamespace(size=sizes[key], content_type="application/pdf"))
    provider = Mock(return_value={"url": "https://upload.example.test", "method": "PUT"})
    monkeypatch.setattr(receipt_storage, "presigned_upload", provider)
    monkeypatch.setattr(machine_storage, "presigned_upload", provider)
    return space, callers(space, surface, settings, monkeypatch), sizes, provider


def command(space, kind, index):
    if kind == "receipt":
        row = ToBuyItem.objects.create(makerspace=space, name=f"Purchase {index}", kind="hardware")
        url = reverse("procurement:to-buy-receipt-list", args=[row.pk])
        presign = reverse("procurement:to-buy-receipt-presign", args=[row.pk])
        return url, presign, {"object_key": f"procurement/{space.pk}/p4a-{index}.pdf"}
    machine_type, _ = MachineType.objects.get_or_create(makerspace=space, slug="p4a-type", defaults={"name": "Type"})
    if kind == "machine_document":
        row = Machine.objects.create(makerspace=space, machine_type=machine_type, name=f"Machine {index}")
        return reverse("admin-machine-documents", args=[row.pk]), reverse("admin-machine-document-presign", args=[row.pk]), {
            "object_key": f"machines/{space.pk}/p4a-{index}.pdf", "doc_type": "manual", "original_filename": "guide.pdf"}
    url = reverse("machine-type-documents", args=[space.pk, machine_type.pk])
    presign = reverse("machine-type-document-presign", args=[space.pk, machine_type.pk])
    return url, presign, {"object_key": f"machines/{space.pk}/p4a-{index}.pdf",
                          "title": "Guide", "original_filename": "guide.pdf"}


def snapshot(space):
    return (Makerspace.objects.get(pk=space.pk).storage_bytes_used,
            list(ToBuyReceipt.objects.order_by("pk").values()),
            list(MachineTypeDocument.objects.order_by("pk").values()),
            list(MachineDocument.objects.order_by("pk").values()),
            list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()))


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("key,status,code", KEYS)
def test_private_upload_max_and_next_refusal_has_no_attachment_or_charge(
        surface, kind, key, status, code, settings, monkeypatch):
    space, pair, sizes, _ = world(key, surface, settings, monkeypatch)
    commands = [command(space, kind, index) for index in range(2)]
    sizes[commands[0][2]["object_key"]] = 10
    sizes[commands[1][2]["object_key"]] = 11 if key == "upload_bytes" else 1
    maximum = pair[0].post(commands[0][0], commands[0][2], format="json")
    assert maximum.status_code == 201, maximum.content
    before = snapshot(space)
    refused = pair[0].post(commands[1][0], commands[1][2], format="json")
    assert (refused.status_code, refused.json()["code"]) == (status, code)
    assert snapshot(space) == before
    assert before[0] == 10


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("key,status,code", KEYS[1:])
def test_private_upload_race_keeps_one_attachment_and_one_charge(
        surface, kind, key, status, code, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, pair, sizes, _ = world(key, surface, settings, monkeypatch)
    commands = [command(space, kind, index) for index in range(2)]
    sizes.update({body["object_key"]: 10 for _, _, body in commands})
    results = race(pair, [("post", url, body, 201) for url, _, body in commands])
    assert sorted(actual for actual, _ in results) == [201, status]
    assert [body["code"] for actual, body in results if actual == status] == [code]
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10
    model = {"receipt": ToBuyReceipt, "type_document": MachineTypeDocument, "machine_document": MachineDocument}[kind]
    assert model.objects.count() == 1


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", KINDS)
def test_private_presign_refuses_full_storage_before_provider(kind, surface, settings, monkeypatch):
    space, pair, _, provider = world("storage", surface, settings, monkeypatch)
    _, url, _ = command(space, kind, 0)
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=10)
    before = snapshot(space)
    refused = pair[0].post(url, {"filename": "guide.pdf", "content_type": "application/pdf"}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "upload_limit")
    assert snapshot(space) == before
    provider.assert_not_called()


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind,key,field,code", [
    ("receipt", "inventory.tobuy", "enabled_features", "not_found"),
    ("type_document", "machines", "enabled_modules", "module_disabled"),
    ("machine_document", "machines", "enabled_modules", "module_disabled")])
def test_private_upload_switch_off_preserves_attachments_and_on_restores(
        surface, kind, key, field, code, settings, monkeypatch):
    space, pair, sizes, _ = world("storage", surface, settings, monkeypatch)
    url, _, body = command(space, kind, 0)
    sizes[body["object_key"]] = 10
    original = list(getattr(space, field))
    assert key in original
    setattr(space, field, [value for value in original if value != key])
    space.save(update_fields=[field])
    before = snapshot(space)
    refused = pair[0].post(url, body, format="json")
    assert (refused.status_code, refused.json()["code"]) == (404, code)
    assert snapshot(space) == before
    setattr(space, field, original)
    space.save(update_fields=[field])
    assert pair[0].post(url, body, format="json").status_code == 201
