"""SECFIX-A: device webhook pushes and the image adapter on the shared pinned transport (security review M1,
lead 2/7/8, L-C1, L-C2, M10, hardening 22)."""
import socket
from io import BytesIO

import pytest
from django.urls import reverse

from apps import outbound_http, outbound_policy
from apps.card_designs import cutouts
from apps.card_designs.image_adapter import client as eraser
from apps.card_designs.image_adapter import png_validation
from apps.card_designs.image_adapter.errors import AdapterError
from apps.card_designs.models import CardPhotoCutout, MakerspaceImageAdapter
from apps.devices import services_adapter_webhook as push
from apps.devices.models import AdapterWebhookDelivery
from apps.makerspaces.models import Makerspace
from tests.l3_local.helpers import card_space, client, manager
from tests.parity_0120.adapter_api.adapter_case import adapter_case
from tests.parity_0120.bg_eraser.conftest import card_test_host, cutout_png, jpeg, original_photo, store  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)
URL = "https://hooks.example.com/spaceworks"
SECRET = "a-very-long-shared-secret-1234"


def _dns(*ips, port=443):
    return lambda *a, **k: [((socket.AF_INET6 if ":" in ip else socket.AF_INET), 1, 6, "", (ip, port)) for ip in ips]


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr("apps.devices.tasks.deliver_adapter_webhook_task.delay", lambda *a, **k: None)
    monkeypatch.setattr("apps.card_designs.tasks.dispatch_cutout", lambda cutout_id: None)


def _hook(case, url=URL):
    return case["client"].put(reverse("devices:admin-adapter-webhook", args=[case["device"].pk]), {"url": url},
                              format="json")


# --- webhook pushes ----------------------------------------------------------------------------------------------
def test_a_push_url_on_another_port_is_refused(monkeypatch):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("93.184.216.34", port=22))
    case = adapter_case("secfix-push-port")
    refused = _hook(case, "https://hooks.example.com:22/x")
    assert refused.status_code == 400 and refused.data["code"] == "webhook_url_refused"


def test_a_name_that_rebinds_to_a_private_address_at_send_time_is_never_dialled(monkeypatch):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("93.184.216.34"))
    case = adapter_case("secfix-push-rebind")
    assert _hook(case).status_code == 200
    row = push.wake(case["device"], "ping")
    answers = iter([_dns("93.184.216.34")(), _dns("10.0.0.7")()])  # the claim check, then the send-time lookup
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", lambda *a, **k: next(answers))
    monkeypatch.setattr(outbound_http, "send", lambda *a, **k: pytest.fail("a refused name is never dialled"))
    assert push.deliver(row.pk) == "failed"
    row.refresh_from_db()
    assert row.last_error == "url_refused" and row.last_status_code is None


def test_a_push_dials_the_pinned_address_with_a_cap_and_one_deadline(monkeypatch):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("93.184.216.34"))
    case = adapter_case("secfix-push-ok")
    _hook(case)
    row = push.wake(case["device"], "ping")
    seen = {}

    def send(target, method, **kwargs):
        seen.update(kwargs, ip=target.addresses[0].ip, host=target.host_header, method=method)
        return outbound_http.Response(204)
    monkeypatch.setattr(outbound_http, "send", send)
    assert push.deliver(row.pk) == "delivered"
    assert seen["ip"] == "93.184.216.34" and seen["host"] == "hooks.example.com" and seen["method"] == "POST"
    assert seen["max_bytes"] == push.REPLY_BYTES and seen["truncate"] is True
    assert seen["deadline"] == push.TIMEOUT_SECONDS


def test_a_failed_push_keeps_no_status_code_or_network_detail(monkeypatch):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("93.184.216.34"))
    case = adapter_case("secfix-push-oracle")
    _hook(case)
    for outcome in (lambda *a, **k: outbound_http.Response(502), "timeout", "unreachable"):
        row = push.wake(case["device"], "ping")
        if callable(outcome):
            monkeypatch.setattr(outbound_http, "send", outcome)
        else:
            def boom(*_a, _reason=outcome, **_k):
                raise outbound_http.OutboundError(_reason)
            monkeypatch.setattr(outbound_http, "send", boom)
        push.deliver(row.pk)
        row.refresh_from_db()
        assert (row.last_status_code, row.last_error) == (None, "delivery_failed")
    assert AdapterWebhookDelivery.objects.filter(last_error="delivery_failed").count() == 3


# --- image adapter: addresses and the transport ------------------------------------------------------------------
@pytest.mark.parametrize("address", ["100.100.100.200", "100.64.0.1", "169.254.169.254", "10.0.0.5"])
def test_a_space_provider_on_a_non_public_address_is_refused_at_call_time(monkeypatch, address):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns(address))
    monkeypatch.setattr(outbound_http, "send", lambda *a, **k: pytest.fail("never dialled"))
    with pytest.raises(AdapterError) as caught:
        eraser.test_connection(eraser.ProviderConfig("https://eraser.example.org", "s" * 24, "space"))
    assert caught.value.code == "url_not_allowed"


def test_the_platform_provider_may_be_private_but_never_metadata(monkeypatch):
    config = eraser.ProviderConfig("http://bg-eraser:8080", "s" * 24, "platform")
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("169.254.169.254", port=8080))
    with pytest.raises(AdapterError) as caught:
        eraser.test_connection(config)
    assert caught.value.code == "url_not_allowed"
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("172.20.0.4", port=8080))
    seen = {}

    def send(target, method, **kwargs):
        seen.update(kwargs, ip=target.addresses[0].ip)
        return outbound_http.Response(200, {"content-type": "application/json"},
                                      b'{"contract": "1", "capabilities": ["image.remove_background"]}')
    monkeypatch.setattr(outbound_http, "send", send)
    assert eraser.test_connection(config)["ok"] is True
    assert seen["ip"] == "172.20.0.4" and seen["max_bytes"] == eraser.HEALTH_BYTES
    assert seen["deadline"] == eraser.HEALTH_DEADLINE


def test_a_slow_provider_is_a_typed_timeout(monkeypatch):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("93.184.216.34"))

    def slow(*_a, **_k):
        raise outbound_http.OutboundError("timeout")
    monkeypatch.setattr(outbound_http, "send", slow)
    with pytest.raises(AdapterError) as caught:
        eraser.test_connection(eraser.ProviderConfig("https://eraser.example.org", "s" * 24, "space"))
    assert caught.value.code == "provider_timeout"


def test_a_provider_returned_mask_url_is_pinned_and_held_to_the_public_rule(monkeypatch):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("100.100.100.200"))
    monkeypatch.setattr(outbound_http, "send", lambda *a, **k: pytest.fail("never dialled"))
    with pytest.raises(AdapterError) as caught:
        eraser._fetch_mask("https://masks.example.org/m.png")
    assert caught.value.code == "url_not_allowed"
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("93.184.216.34"))
    monkeypatch.setattr(outbound_http, "send", lambda target, method, **k: outbound_http.Response(200, {}, b"PNG"))
    assert eraser._fetch_mask("https://masks.example.org/m.png") == b"PNG"


# --- image adapter: decode-after-size (lead 7 / L-C1) -------------------------------------------------------------
def _huge_png(width=6000, height=1000):
    from PIL import Image
    out = BytesIO()
    Image.new("L", (width, height)).save(out, format="PNG", optimize=True)  # all zeros: compresses to a few KB
    return out.getvalue()


def test_an_oversized_png_is_refused_from_its_header_before_any_decode(monkeypatch):
    data = _huge_png()
    assert len(data) < 1024 * 1024  # inside the byte limit: only the header check stops it
    from PIL import ImageFile
    monkeypatch.setattr(ImageFile.ImageFile, "load", lambda self: pytest.fail("decoded before the size check"))
    for call in (lambda: png_validation.validate_png(data, (100, 100)),
                 lambda: png_validation.apply_mask(jpeg(), data, (40, 60))):
        with pytest.raises(AdapterError) as caught:
            call()
        assert caught.value.code == "response_shape_mismatch"


def test_a_normal_cutout_still_validates():
    data, width, height = png_validation.validate_png(cutout_png(), (40, 60))
    assert (width, height) == (40, 60) and data.startswith(b"\x89PNG")


# --- provider settings (hardening 22) and the test throttle (L-C2) -----------------------------------------------
def test_changing_a_space_providers_address_needs_the_secret_again(monkeypatch):
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("93.184.216.34"))
    space = card_space("secfix-eraser-url", features=("cards.photo_cutout",))
    api = client(manager(space))
    url = reverse("admin-image-adapter", args=[space.pk])
    assert api.patch(url, {"provider_url": "https://one.example.org", "secret": SECRET}, format="json").status_code == 200
    moved = api.patch(url, {"provider_url": "https://two.example.org"}, format="json")
    assert moved.status_code == 400 and "secret" in moved.json()
    assert MakerspaceImageAdapter.objects.get(makerspace=space).provider_url == "https://one.example.org"
    assert api.patch(url, {"provider_url": "https://one.example.org"}, format="json").status_code == 200
    assert api.patch(url, {"provider_url": "https://two.example.org", "secret": SECRET + "2"},
                     format="json").status_code == 200


def test_the_provider_test_route_is_throttled_per_user(monkeypatch):
    from django.core.cache import cache

    from apps.outbound_throttles import ImageAdapterTestThrottle
    monkeypatch.setattr(outbound_policy.socket, "getaddrinfo", _dns("93.184.216.34"))
    monkeypatch.setattr(outbound_http, "send", lambda *a, **k: outbound_http.Response(503))
    # The scope is now configured in REST_FRAMEWORK (settings_drf), which wins over `default_rate`.
    monkeypatch.setitem(ImageAdapterTestThrottle.THROTTLE_RATES, "image_adapter_test", "2/min")
    cache.clear()
    space = card_space("secfix-eraser-throttle", features=("cards.photo_cutout",))
    api = client(manager(space))
    api.patch(reverse("admin-image-adapter", args=[space.pk]),
              {"provider_url": "https://one.example.org", "secret": SECRET}, format="json")
    test_url = reverse("admin-image-adapter-test", args=[space.pk])
    assert [api.post(test_url).status_code for _ in range(3)] == [200, 200, 429]


# --- cut-out storage compensation (lead 8 / M10) -----------------------------------------------------------------
def _queued_cutout(slug):
    from tests.l3_local.helpers import issue, member
    from tests.parity_0120.bg_eraser.conftest import set_photo
    from apps.card_designs.models import PlatformImageAdapter
    space = card_space(slug, features=("cards.photo_cutout",))
    row = PlatformImageAdapter()
    row.provider_url = "https://eraser.example.org"
    row.set_secret("s" * 24)
    row.save()
    sm = manager(space)
    _user, membership = member(space)
    card = issue(space, membership, by=sm)
    set_photo(card, "member-cards/1/original")
    client(sm).post(reverse("admin-member-card-photo-cutout", args=[card.pk]), {}, format="json")
    return space, CardPhotoCutout.objects.get()


def test_a_cutout_refused_at_the_storage_cap_frees_nothing(monkeypatch, store, original_photo):  # noqa: F811
    space, row = _queued_cutout("secfix-cut-cap")
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=5000)
    monkeypatch.setattr(cutouts.client, "remove_background", lambda *a: (cutout_png(), 40, 60))

    def full(*_a, **_k):
        raise RuntimeError("storage cap reached")
    monkeypatch.setattr("apps.makerspaces.limits_usage.add_storage", full)
    cutouts.run(row.pk)
    row.refresh_from_db()
    assert row.state == "failed" and row.error_code == "storage_unavailable"
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 5000  # existing usage untouched


def test_a_cutout_that_fails_after_charging_gives_the_bytes_back(monkeypatch, store, original_photo):  # noqa: F811
    space, row = _queued_cutout("secfix-cut-put")
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=5000)
    monkeypatch.setattr(cutouts.client, "remove_background", lambda *a: (cutout_png(), 40, 60))

    def broken_put(*_a, **_k):
        raise RuntimeError("bucket down")
    monkeypatch.setattr(cutouts, "put_bytes", broken_put)
    cutouts.run(row.pk)
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 5000  # charged, then released
