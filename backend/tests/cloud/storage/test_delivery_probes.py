from dataclasses import replace
from unittest.mock import Mock

import pytest

from apps.storage_capabilities import delivery_probes
from apps.storage_capabilities.contracts import CapabilityError, StorageIdentity
from tests.cloud.storage.test_contracts import contract


def setup(monkeypatch):
    private = contract()
    public = replace(contract(), identity=StorageIdentity.build("https://s3.example.test", "auto", "images"), public_delivery="public")
    private_client, public_client, signing_client = Mock(), Mock(), Mock()
    identities = {id(private_client): private.identity, id(public_client): public.identity}
    monkeypatch.setattr(delivery_probes, "client_identity", lambda client, bucket: identities[id(client)])
    monkeypatch.setattr(delivery_probes, "delete_exact_key", Mock())
    signing_client.generate_presigned_url.return_value = "https://s3.example.test/private/staged?signature=redacted"
    options = dict(private_client=private_client, public_client=public_client, signing_client=signing_client,
                   private_contract=private, public_contract=public, public_base_url="https://images.example",
                   frontend_origins=["https://space.example"])
    return options


def test_private_staging_public_final_signed_read_and_cors_are_independent(monkeypatch):
    options = setup(monkeypatch)
    payload = delivery_probes.PROBE_IMAGE
    responses = Mock(side_effect=[(200, payload, {}), (403, b"", {}), (200, payload, {}),
        (204, b"", {"Access-Control-Allow-Origin": "https://space.example", "Access-Control-Allow-Methods": "GET, HEAD, PUT"})])
    monkeypatch.setattr(delivery_probes, "_http", responses)
    result = delivery_probes.probe_delivery(**options)
    assert result["private_staging"] == "denied"
    assert result["public_delivery"] == "verified"
    assert "signature" not in str(result)
    assert options["private_client"].put_object.call_args.kwargs["Key"].startswith("staging/public-images/")
    assert delivery_probes.delete_exact_key.call_count == 2


def test_anonymous_staging_read_is_a_failure_even_if_signed_read_works(monkeypatch):
    options = setup(monkeypatch)
    payload = delivery_probes.PROBE_IMAGE
    monkeypatch.setattr(delivery_probes, "_http", Mock(side_effect=[(200, payload, {}), (200, b"", {})]))
    with pytest.raises(CapabilityError, match="publicly_readable"):
        delivery_probes.probe_delivery(**options)
    options["public_client"].put_object.assert_not_called()
