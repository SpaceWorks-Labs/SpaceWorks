"""Decision 540: real serializer -> reservation -> bounded PUT at HTTP boundaries."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.evidence import storage as evidence_storage
from apps.inventory import public_image_storage
from apps.machines import storage as document_storage
from apps.machines.models import Machine, MachineType
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from apps.storage_capabilities import presigning
from tests.cloud.storage.test_contracts import contract
from tests.l3_local.helpers import card_space, client, issue, manager, member
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory,
              pytest.mark.area_membership, pytest.mark.area_machines]


@pytest.fixture
def world(settings, monkeypatch):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.MANAGED_PLANS_ENABLED = False
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.STORAGE_CAPABILITIES_FILE = "proven-put-only-contract"
    settings.STORAGE_PRESIGN_METHOD = "auto"
    settings.PUBLIC_IMAGE_MAX_BYTES = 8
    settings.MACHINE_DOC_MAX_BYTES = 8
    settings.EVIDENCE_MAX_BYTES = 8
    provider = Mock(meta=SimpleNamespace(endpoint_url="https://storage.test"))
    provider.generate_presigned_url.return_value = "https://storage.test/put"
    value = contract(max_object_bytes=8)
    monkeypatch.setattr(presigning, "capabilities_for", lambda *a, **kw: value)
    monkeypatch.setattr(presigning, "verified_state", lambda *a: SimpleNamespace(facts={"presign_methods": ["put"]}))
    for module in (public_image_storage, document_storage, evidence_storage):
        monkeypatch.setattr(module, "_client", lambda: provider)
        monkeypatch.setattr(module, "_public_client", lambda: provider)
    space = card_space("r2-put-http", modules=("membership", "member_accounts", "email", "machines", "public_inventory"))
    staff = manager(space)
    holder, membership = member(space)
    card = issue(space, membership, by=staff)
    product = make_product(space)
    kind = MachineType.objects.create(makerspace=space, name="Laser", slug="r2-laser")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="Laser")
    return space, staff, holder, card, product, machine, provider


def boundary(world, area):
    space, staff, holder, card, product, machine, provider = world
    if area == "image":
        return client(staff), reverse("admin-inventory-image", args=[product.pk]), {"filename": "image.png", "content_type": "image/png"}
    if area == "document":
        return client(staff), reverse("admin-machine-document-presign", args=[machine.pk]), {"filename": "manual.pdf", "content_type": "application/pdf"}
    return client(holder), reverse("member-card-photo", args=[space.pk]), {"content_type": "image/png"}


def snapshot(world):
    space, _, _, card, product, machine, _ = world
    return (
        list(StorageQuotaReservation.objects.values()), list(AuditLog.objects.order_by("pk").values()),
        Makerspace.objects.get(pk=space.pk).storage_bytes_used,
        type(card).objects.filter(pk=card.pk).values().get(),
        type(product).objects.filter(pk=product.pk).values().get(),
        list(machine.documents.values()),
    )


@pytest.mark.parametrize("area", ["image", "card", "document"])
@pytest.mark.parametrize("size", [4, 8])
def test_configured_put_only_http_reserves_and_signs_the_actual_size(world, area, size, settings):
    api, url, body = boundary(world, area)
    response = api.post(url, {**body, "size": size}, format="json")
    assert response.status_code == 201, response.data
    payload = response.data["upload"] if area == "document" else response.data
    assert payload["method"] == "PUT"
    assert payload["headers"] == {"Content-Type": body["content_type"], "Content-Length": str(size)}
    key = response.data["object_key"]
    reservation = StorageQuotaReservation.objects.get(object_key=key)
    assert (reservation.size_bytes, reservation.converted, reservation.released) == (size, False, False)
    provider = world[-1]
    provider.generate_presigned_url.assert_called_once_with("put_object", Params={
        "Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": reservation.staging_key,
        "ContentType": body["content_type"], "ContentLength": size,
    }, ExpiresIn=settings.PUBLIC_IMAGE_URL_TTL_SECONDS if area == "image" else settings.EVIDENCE_URL_TTL_SECONDS)
    provider.generate_presigned_post.assert_not_called()
    assert Makerspace.objects.get(pk=world[0].pk).storage_bytes_used == 0


@pytest.mark.parametrize("area", ["image", "card", "document"])
@pytest.mark.parametrize("size,code", [(9, "upload_limit"), (None, "upload_size_required")])
def test_put_only_http_refuses_oversize_or_omitted_size_without_a_policy_or_write(world, area, size, code):
    api, url, body = boundary(world, area)
    before = snapshot(world)
    response = api.post(url, {**body, **({"size": size} if size is not None else {})}, format="json")
    assert (response.status_code, response.data["code"]) == (400, code)
    assert snapshot(world) == before
    world[-1].generate_presigned_url.assert_not_called()
    world[-1].generate_presigned_post.assert_not_called()


@pytest.mark.parametrize("area", ["image", "card", "document"])
@pytest.mark.parametrize("key,status,code", [
    ("upload_bytes", 400, "upload_limit"), ("storage", 400, "limit_reached"),
    ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached"),
])
def test_declared_size_respects_each_tenant_ceiling_before_authorization(world, area, key, status, code):
    space = world[0]
    space.resource_limit_overrides = {key: 3}
    space.save(update_fields=["resource_limit_overrides"])
    api, url, body = boundary(world, area)
    before = snapshot(world)
    response = api.post(url, {**body, "size": 4}, format="json")
    assert (response.status_code, response.data["code"]) == (status, code)
    assert snapshot(world) == before
    world[-1].generate_presigned_url.assert_not_called()
    world[-1].generate_presigned_post.assert_not_called()
