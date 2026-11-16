from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from apps.events.credentials.streaming import private_bytes


def test_range_headers_and_private_body_use_shared_transport():
    request = APIRequestFactory().get("/print/download/", HTTP_RANGE="bytes=2-5")
    calls = []
    response = private_bytes(request, b"0123456789", authorize=lambda: calls.append(True),
        expires_at=timezone.now()+timedelta(minutes=1), mime="application/pdf", locator_key="private/key")
    assert response.status_code == 206
    assert response["Content-Range"] == "bytes 2-5/10"
    assert response["Cache-Control"] == "private, no-store"
    assert b"".join(response.streaming_content) == b"2345"
    assert len(calls) >= 3


def test_revocation_between_chunks_stops_bytes_already_authorized_url_cannot_bypass():
    revoked = False
    def authorize():
        if revoked:
            raise PermissionDenied()
    request = APIRequestFactory().get("/print/download/")
    response = private_bytes(request, b"a"*(2*1024*1024), authorize=authorize,
        expires_at=timezone.now()+timedelta(minutes=1), mime="image/png", locator_key="private/key")
    stream = iter(response.streaming_content)
    assert len(next(stream)) == 1024*1024
    revoked = True
    with pytest.raises(PermissionDenied):
        next(stream)


def test_invalid_multi_range_is_416_and_head_has_no_body():
    request = APIRequestFactory().get("/print/download/", HTTP_RANGE="bytes=0-1,4-5")
    response = private_bytes(request, b"123456", authorize=lambda: None,
        expires_at=timezone.now()+timedelta(minutes=1), mime="image/png", locator_key="private/key")
    assert response.status_code == 416 and response["Content-Range"] == "bytes */6"
    request = APIRequestFactory().head("/print/download/")
    response = private_bytes(request, b"123456", authorize=lambda: None,
        expires_at=timezone.now()+timedelta(minutes=1), mime="image/png", locator_key="private/key")
    assert response.content == b"" and response["Content-Length"] == "6"
