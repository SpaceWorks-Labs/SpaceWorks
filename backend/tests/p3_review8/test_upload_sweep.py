"""Other Phase-2 upload mechanisms already avoid writable final-key presigns."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.events import certificate_artwork_storage
from apps.makerspaces import limits, website_assets
from .conftest import png


@pytest.mark.django_db
@pytest.mark.parametrize("module", ["events", "bookings"])
def test_website_assets_are_server_converted_and_charge_only_final_bytes(world, monkeypatch, module):
    values, writes = {}, []
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    def put(key, data, mime):
        writes.append((key, mime))
        values[key] = data
    monkeypatch.setattr(website_assets, "_put", put)
    monkeypatch.setattr(website_assets, "delete_object", lambda key: values.pop(key, None))
    # A multipart body has no client-selected object key or reusable presign.
    page = SimpleNamespace(pk=42, makerspace_id=world.space.pk, makerspace=world.space)
    copies = SimpleNamespace(created=[])
    key, size = website_assets.upload(BytesIO(png()), module=module, page=page, copies=copies)
    assert key.startswith(f"{module}/website/{world.space.pk}/42/")
    assert writes == [("staging/" + key, "application/octet-stream"), (key, "image/webp")]
    assert set(values) == {key} and values[key].startswith(b"RIFF")
    assert size == len(values[key])
    world.space.refresh_from_db()
    assert world.space.storage_bytes_used == size


def test_certificate_artwork_presign_remains_staging_only(monkeypatch):
    client = Mock()
    monkeypatch.setattr(certificate_artwork_storage, "_client", lambda _: client)
    row = SimpleNamespace(object_key="events/1/artwork/image.png")
    certificate_artwork_storage.upload_url(row, content_type="image/png", content_length=100)
    params = client.generate_presigned_url.call_args.kwargs["Params"]
    assert params["Key"] == "staging/" + row.object_key
    assert params["ContentType"] == "image/png" and params["ContentLength"] == 100
