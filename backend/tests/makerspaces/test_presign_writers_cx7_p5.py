"""All ordinary tenant presign backends reserve before calling their providers."""
import importlib
from itertools import combinations_with_replacement
from unittest.mock import Mock

import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.makerspaces.models import StorageQuotaReservation
from apps.makerspaces.storage_reservations import reserved_bytes
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_bookings,
              pytest.mark.area_machines, pytest.mark.area_machine_service, pytest.mark.area_membership]
WRITERS = [
    ("inventory.public_image_storage", "presigned_upload", "items", "PUBLIC_IMAGE_MAX_BYTES", False),
    ("bookings.storage", "presigned_upload", "spaces", "PUBLIC_IMAGE_MAX_BYTES", False),
    ("procurement.storage", "presigned_upload", "procurement", "PROCUREMENT_RECEIPT_MAX_BYTES", False),
    ("machines.storage", "presigned_upload", "machines", "MACHINE_DOC_MAX_BYTES", False),
    ("maintenance.storage", "presigned_upload", "machines", "MACHINE_DOC_MAX_BYTES", False),
    ("warranty.storage", "presigned_upload", "warranty", "WARRANTY_DOC_MAX_BYTES", False),
    ("machines.service_storage", "presigned_upload", "machine", "EVIDENCE_MAX_BYTES", True),
    ("maintenance.repairs.storage", "presign", "repairs", "EVIDENCE_MAX_BYTES", False),
    ("card_designs.storage", "presign_staging", "card-assets", "EVIDENCE_MAX_BYTES", True),
    ("evidence.storage", "presigned_upload", "member-cards", "EVIDENCE_MAX_BYTES", True),
]


def setup(writer, settings, monkeypatch, space=None):
    module_name, method, prefix, ceiling, explicit = writer
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.MANAGED_PLANS_ENABLED = False
    setattr(settings, ceiling, 1)
    space = space or make_space("p5-writer")
    space.resource_limit_overrides = {"storage": 1}
    space.save(update_fields=["resource_limit_overrides"])
    module = importlib.import_module("apps." + module_name)
    sdk = Mock()
    sdk.meta.endpoint_url = "https://storage.test"
    sdk.generate_presigned_post.return_value = {"url": "https://upload.test", "fields": {}}
    sdk.generate_presigned_url.return_value = "https://upload.test"
    # The storage SDK boundary is replaced; real wrappers, quota resolution and
    # transactions remain. Card and member-photo transports use the shared signer.
    monkeypatch.setattr(module, "_public_client", lambda: sdk, raising=False)
    monkeypatch.setattr(module, "_client", lambda: sdk, raising=False)
    monkeypatch.setattr("apps.evidence.storage._public_client", lambda: sdk)
    monkeypatch.setattr("apps.evidence.storage._client", lambda: sdk)
    provider = Mock(return_value={"url": "https://upload.test", "fields": {}})
    monkeypatch.setattr("apps.private_uploads.presign_upload", provider)
    monkeypatch.setattr("apps.inventory.public_image_cloud.presign_upload", provider)
    monkeypatch.setattr("apps.evidence.storage.presign_upload", provider)

    def create(index):
        args = [f"{prefix}/{space.pk}/object-{index}.png", "image/png"]
        if explicit:
            args.append(1)
        return getattr(module, method)(*args, exact_bytes=1)

    return space, create, sdk, provider


@pytest.mark.parametrize("transport", ["put", "post"])
@pytest.mark.parametrize("writer", WRITERS, ids=lambda row: row[0])
def test_presign_backend_max_next_refusal_never_signs_excess(writer, transport, settings, monkeypatch):
    settings.STORAGE_PRESIGN_METHOD = transport
    space, create, sdk, provider = setup(writer, settings, monkeypatch)
    create(0)
    assert reserved_bytes(space) == 1
    calls = sdk.mock_calls[:], provider.mock_calls[:]
    with pytest.raises(APIException) as failure:
        create(1)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (400, "limit_reached")
    assert (sdk.mock_calls, provider.mock_calls) == calls
    assert StorageQuotaReservation.objects.filter(makerspace=space).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("writer", WRITERS, ids=lambda row: row[0])
def test_each_presign_backend_serializes_the_last_slot(writer, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.STORAGE_PRESIGN_METHOD = "post"
    space, create, _, _ = setup(writer, settings, monkeypatch)
    assert race_creators(create) == [(201, "created"), (400, "limit_reached")]
    assert reserved_bytes(space) == 1


def test_account_namespace_never_interprets_a_person_id_as_tenant_id(settings, monkeypatch):
    from apps.inventory import public_image_storage
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.STORAGE_PRESIGN_METHOD = "post"
    sdk = Mock()
    sdk.meta.endpoint_url = "https://storage.test"
    sdk.generate_presigned_post.return_value = {"url": "https://upload.test", "fields": {}}
    monkeypatch.setattr(public_image_storage, "_public_client", lambda: sdk)
    assert public_image_storage.presigned_upload("account/987654321/image.png", "image/png")["url"] == "https://upload.test"
    assert StorageQuotaReservation.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("writers", list(combinations_with_replacement(WRITERS, 2)),
                         ids=lambda pair: pair[0][0] + "+" + pair[1][0])
def test_mixed_presign_backends_share_the_last_tenant_storage_slot(writers, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.STORAGE_PRESIGN_METHOD = "post"
    space, first, _, _ = setup(writers[0], settings, monkeypatch)
    _, second, _, _ = setup(writers[1], settings, monkeypatch, space)
    commands = [first, second]
    assert race_creators(lambda index: commands[index](index)) == [(201, "created"), (400, "limit_reached")]
    assert reserved_bytes(space) == 1
