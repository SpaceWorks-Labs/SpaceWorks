import io
from unittest.mock import Mock

import pytest

from apps.storage_capabilities import upload_probes
from apps.storage_capabilities.contracts import CapabilityError
from tests.cloud.storage.test_contracts import contract


def test_post_qualification_tests_real_success_size_and_mime_rejections(monkeypatch):
    s3 = Mock()
    s3.generate_presigned_post.return_value = {"url": "https://api.example", "fields": {}}
    s3.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(b"valid")}
    post = Mock(side_effect=[204, 400, 403])
    monkeypatch.setattr(upload_probes, "_post", post)
    deleted = Mock()
    monkeypatch.setattr(upload_probes, "delete_exact_key", deleted)
    facts = upload_probes.probe_upload_methods(s3, contract(presign_methods=frozenset({"post"})))
    assert facts == {"presign_methods": ["post"], "post_size_policy": True}
    assert [call.args[1:] for call in post.call_args_list] == [
        (b"valid", "image/png"), (b"x" * 17, "image/png"), (b"valid", "application/pdf"),
    ]
    assert deleted.call_count == 1


def test_post_provider_ignoring_size_policy_is_refused_and_cleaned(monkeypatch):
    s3 = Mock()
    s3.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(b"valid")}
    monkeypatch.setattr(upload_probes, "_post", lambda *args: 204)
    deleted = Mock()
    monkeypatch.setattr(upload_probes, "delete_exact_key", deleted)
    with pytest.raises(CapabilityError, match="size_policy_unproven"):
        upload_probes.probe_upload_methods(s3, contract(presign_methods=frozenset({"post"})))
    assert deleted.call_count == 1


def test_put_qualification_requires_signed_exact_mime(monkeypatch):
    s3 = Mock()
    s3.generate_presigned_url.return_value = "https://api.example/signed"
    s3.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(b"valid")}
    request = Mock(side_effect=[200, 403])
    monkeypatch.setattr(upload_probes, "_request", request)
    monkeypatch.setattr(upload_probes, "delete_exact_key", Mock())
    facts = upload_probes.probe_upload_methods(s3, contract())
    assert facts == {"presign_methods": ["put"], "put_size_validation": "finalization"}
    assert request.call_args_list[0].args[0].headers["Content-type"] == "image/png"
