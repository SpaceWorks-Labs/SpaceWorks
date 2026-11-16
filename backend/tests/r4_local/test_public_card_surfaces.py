"""R4 security: certificate share images, public verify throttles, ID programme reads and card
image decoding. Local only."""

import struct
import zlib
from io import BytesIO
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from PIL import Image
from rest_framework.exceptions import ValidationError
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.card_designs.images import normalise
from apps.card_designs.views_holder_photo import MyCardPhotoView
from apps.events.certificates.verification import CertificateVerificationView
from apps.events.profile_photos.views_public import PublicCardPhotoView
from apps.id_programmes.views_public import PublicProgrammeDetailView, PublicProgrammeListView
from tests.idcards_best.certs.test_c7_c10_outputs import _rendered, public_get


def _drawn(monkeypatch):
    texts = []
    from apps.events.certificates import text_rendering  # outputs imports draw_text from here per call
    real = text_rendering.draw_text
    monkeypatch.setattr(text_rendering, "draw_text",
                        lambda canvas, text, *a, **k: (texts.append(text), real(canvas, text, *a, **k))[1])
    return texts


@pytest.mark.django_db(transaction=True)
def test_a_revoked_share_image_never_names_the_holder(monkeypatch):
    _space, _event, _member, row = _rendered("r4-share")
    type(row).objects.filter(pk=row.pk).update(holder_name_public=True)
    texts = _drawn(monkeypatch)
    assert public_get(f"/api/v1/public/event-certificates/{row.serial}/share.png").status_code == 200
    assert "Ada Lovelace" in texts
    texts.clear()
    type(row).objects.filter(pk=row.pk).update(status="revoked")
    assert public_get(f"/api/v1/public/event-certificates/{row.serial}/share.png").status_code == 200
    assert texts and "Ada Lovelace" not in texts


@pytest.mark.django_db(transaction=True)
def test_verify_is_ip_throttled_whatever_the_caller_sends():
    cache.clear()
    _space, _event, _member, row = _rendered("r4-verify")
    from rest_framework.test import APIClient
    client = APIClient(HTTP_HOST="localhost", HTTP_AUTHORIZATION="Bearer not-a-real-token")
    codes = [client.get(f"/api/v1/public/event-certificates/{row.serial}/verify/").status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429


def test_public_reads_take_no_credentials_and_are_throttled():
    assert CertificateVerificationView.authentication_classes == []
    assert PublicCardPhotoView.authentication_classes == []
    for view in (PublicProgrammeListView, PublicProgrammeDetailView):
        assert view.throttle_scope == "public_read" and view.throttle_classes


def test_attaching_a_holder_photo_is_throttled_but_presign_and_remove_are_not(monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"id_join_upload": "2/hour"})
    cache.clear()
    view = MyCardPhotoView()
    assert MyCardPhotoView.get_throttles is APIView.get_throttles
    assert view.throttle_scope == "id_join_upload"
    user = SimpleNamespace(is_authenticated=True, pk=1)

    def allowed(method):
        (throttle,) = view.get_throttles()
        return throttle.allow_request(SimpleNamespace(method=method, user=user), view)

    assert [allowed(method) for method in ("POST", "PUT", "DELETE", "PUT")] == [True] * 4
    assert not allowed("PUT")
    assert allowed("POST")
    assert allowed("DELETE")


def _png_header(width, height):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00" * 64)) + chunk(b"IEND", b"")


def test_oversized_and_broken_images_are_a_validation_error_not_a_crash():
    for data in (_png_header(5000, 5000), _png_header(30000, 30000)):
        with pytest.raises(ValidationError):
            normalise(data)
    buffer = BytesIO()
    Image.new("RGB", (400, 300), "teal").save(buffer, format="JPEG")
    with pytest.raises(ValidationError):
        normalise(buffer.getvalue()[:600])
    small = BytesIO()
    Image.new("RGB", (120, 80), "teal").save(small, format="PNG")
    png, width, height, _mean = normalise(small.getvalue())
    assert (width, height) == (120, 80) and png.startswith(b"\x89PNG")


def test_a_large_phone_jpeg_is_decoded_at_reduced_scale():
    buffer = BytesIO()
    Image.new("RGB", (6000, 4000), "orange").save(buffer, format="JPEG", quality=40)
    _png, width, height, _mean = normalise(buffer.getvalue(), max_edge=1200)
    assert max(width, height) == 1200
