"""Client behaviour with the provider mocked: error mapping, PNG validation, mask answers, URL policy."""
import json

import pytest

from apps.card_designs.image_adapter import client, contract
from apps.card_designs.image_adapter.errors import AdapterError
from apps.card_designs.image_adapter.png_validation import apply_mask, validate_png

from .conftest import cutout_png, jpeg, png

CONFIG = client.ProviderConfig(url="https://eraser.example.org", secret="s" * 24, scope="platform")


def _answer(monkeypatch, status, kind, body):
    monkeypatch.setattr(client, "_send", lambda *a, **k: (status, kind, body))


def test_a_valid_cutout_png_is_accepted_and_reencoded(monkeypatch):
    _answer(monkeypatch, 200, "image/png", cutout_png())
    data, width, height = client.remove_background(CONFIG, jpeg(), "image/jpeg")
    assert (width, height) == (40, 60) and data.startswith(b"\x89PNG")


@pytest.mark.parametrize("body,code", [
    (b"", "response_empty"),
    (b"not an image at all", "response_not_png"),
    (png(), "response_no_alpha"),  # an opaque PNG: nothing was removed
    (png(alpha=255), "response_no_alpha"),  # RGBA but fully opaque
    (png(alpha=0), "response_empty"),  # fully transparent: nothing kept
    (cutout_png((80, 60)), "response_shape_mismatch"),  # aspect ratio changed
])
def test_png_validation_rejects_bad_answers(body, code):
    with pytest.raises(AdapterError) as caught:
        validate_png(body, (40, 60))
    assert caught.value.code == code


def test_a_jpeg_answer_is_not_a_png():
    with pytest.raises(AdapterError) as caught:
        validate_png(jpeg(), (40, 60))
    assert caught.value.code == "response_not_png"


@pytest.mark.parametrize("status,body,code,retryable", [
    (401, {"error": {"code": "invalid_signature"}}, "invalid_signature", False),
    (413, {"error": {"code": "payload_too_large"}}, "payload_too_large", False),
    (422, {"error": {"code": "no_subject_found"}}, "no_subject_found", False),
    (429, {"error": {"code": "rate_limited"}}, "rate_limited", True),
    (503, {"error": {"code": "unavailable"}}, "unavailable", True),
    (502, {}, "internal_error", True),
    (429, {}, "rate_limited", True),
    (503, {}, "unavailable", True),
])
def test_provider_errors_map_to_typed_codes_and_retryability(monkeypatch, status, body, code, retryable):
    _answer(monkeypatch, status, "application/json", json.dumps(body).encode())
    with pytest.raises(AdapterError) as caught:
        client.remove_background(CONFIG, jpeg(), "image/jpeg")
    assert caught.value.code == code and caught.value.retryable is retryable


def test_an_unknown_provider_code_is_not_retryable(monkeypatch):
    _answer(monkeypatch, 400, "application/json", json.dumps({"error": {"code": "weird", "retryable": True}}).encode())
    with pytest.raises(AdapterError) as caught:
        client.remove_background(CONFIG, jpeg(), "image/jpeg")
    # The provider's own "retryable" flag never makes an unknown code retryable (docs/image-adapters/errors.md).
    assert caught.value.code == "invalid_response" and caught.value.retryable is False


def test_inputs_outside_the_contract_never_leave_the_server(monkeypatch):
    monkeypatch.setattr(client, "_send", lambda *a, **k: pytest.fail("must not call the provider"))
    for data, kind in ((jpeg(), "image/gif"), (b"", "image/png"), (b"x" * (contract.MAX_INPUT_BYTES + 1), "image/png")):
        with pytest.raises(AdapterError) as caught:
            client.remove_background(CONFIG, data, kind)
        assert caught.value.code == "input_not_allowed"


def test_a_mask_answer_is_applied_to_the_original(monkeypatch):
    mask = png(alpha=None, colour=(255, 255, 255))  # opaque RGB mask: converted to L; all-white -> fully opaque -> refused
    with pytest.raises(AdapterError) as caught:
        apply_mask(jpeg(), mask, (40, 60))
    assert caught.value.code == "response_no_alpha"
    from PIL import Image
    from io import BytesIO
    half = Image.new("L", (40, 60), 0)
    half.paste(255, (0, 30, 40, 60))
    buffer = BytesIO()
    half.save(buffer, format="PNG")
    data, width, height = apply_mask(jpeg(), buffer.getvalue(), (40, 60))
    assert (width, height) == (40, 60)
    monkeypatch.setattr(client, "_fetch_mask", lambda url: buffer.getvalue())
    _answer(monkeypatch, 200, "application/json", json.dumps({"mask_url": "https://m.example.org/x.png"}).encode())
    assert client.remove_background(CONFIG, jpeg(), "image/jpeg")[1:] == (40, 60)


def test_a_space_provider_must_be_public_https():
    from rest_framework.exceptions import ValidationError
    from apps.card_designs.image_adapter import url_policy
    for bad in ("http://eraser.example.org", "https://127.0.0.1", "https://localhost", "ftp://x.org",
                "https://user:pw@eraser.example.org", "nonsense"):
        with pytest.raises(ValidationError):
            url_policy.clean_base_url(bad, scope="space")
    assert url_policy.clean_base_url("http://bg-eraser:8080/", scope="platform") == "http://bg-eraser:8080"
    with pytest.raises(AdapterError) as caught:
        client.remove_background(client.ProviderConfig("https://127.0.0.1", "s" * 24, "space"), jpeg(), "image/jpeg")
    assert caught.value.code == "url_not_allowed"


def test_test_connection_checks_version_and_capability(monkeypatch):
    ok = {"status": "ok", "contract": "1", "capabilities": ["image.remove_background"]}
    _answer(monkeypatch, 200, "application/json", json.dumps(ok).encode())
    assert client.test_connection(CONFIG)["ok"] is True
    for broken in ({**ok, "contract": "2"}, {**ok, "capabilities": []}):
        _answer(monkeypatch, 200, "application/json", json.dumps(broken).encode())
        with pytest.raises(AdapterError):
            client.test_connection(CONFIG)
