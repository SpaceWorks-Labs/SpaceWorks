from datetime import datetime, timedelta, timezone

import pytest

from apps.makerspaces.private_upload_transport import (
    MAX_CHUNK_BYTES, ObjectLocator, PrivateTransportError,
    bounded_not_after, resolve_range, stream_private,
)

NOW = datetime(2026, 10, 18, 11, tzinfo=timezone.utc)
LOCATOR = ObjectLocator(bucket="private", key="server-owned", version_id="immutable")


@pytest.mark.parametrize("header,start,end", [
    (None, 0, 99), ("bytes=3-8", 3, 8), ("bytes=90-", 90, 99),
    ("bytes=-10", 90, 99), ("bytes=0-1000", 0, 99), ("bytes=-1000", 0, 99),
])
def test_single_range(header, start, end):
    result = resolve_range(header, 100)
    assert (result.start, result.end, result.length) == (start, end, end-start+1)
    assert result.content_range == f"bytes {start}-{end}/100"


@pytest.mark.parametrize("header", ["bytes=0-1,3-4", "bytes=100-", "bytes=4-3",
                                      "bytes=-0", "bytes=-", "items=0-2", "bytes=" + "9"*100 + "-"])
def test_invalid_and_multiple_ranges_refuse(header):
    with pytest.raises(PrivateTransportError) as exc:
        resolve_range(header, 100)
    assert exc.value.status == 416


def test_ttl_uses_shortest_finite_authority_boundary_and_floors_seconds():
    limits = (None, NOW+timedelta(seconds=50), NOW+timedelta(seconds=12.9))
    assert bounded_not_after(now=NOW, purpose_max_seconds=60, limits=limits) == NOW+timedelta(seconds=12)
    with pytest.raises(PrivateTransportError):
        bounded_not_after(now=NOW, purpose_max_seconds=60, limits=(NOW+timedelta(milliseconds=900),))


def stream(reader, authorize=lambda: None, clock=lambda: NOW, size=1, expiry=None):
    return stream_private(locator=LOCATOR, byte_range=resolve_range(None, size), reader=reader,
                          authorize=authorize, clock=clock, not_after=expiry or NOW+timedelta(seconds=60))


def test_expired_authorized_asset_never_contacts_storage():
    calls = []
    with pytest.raises(PrivateTransportError) as exc:
        list(stream(lambda *a, **k: calls.append(k), expiry=NOW-timedelta(seconds=1)))
    assert exc.value.status == 410 and calls == []


def test_foreign_resource_denial_precedes_expiry_and_storage():
    def deny():
        raise PrivateTransportError("not_found", 404)

    with pytest.raises(PrivateTransportError) as exc:
        list(stream(lambda *a, **k: pytest.fail("Storage must not be called"), deny,
                    expiry=NOW-timedelta(seconds=1)))
    assert exc.value.status == 404


def test_revocation_during_read_withholds_entire_chunk():
    state = {"allowed": True}

    def read(*args, **kwargs):
        assert kwargs["timeout_seconds"] == 2
        state["allowed"] = False
        return b"x"

    def authorize():
        if not state["allowed"]:
            raise PrivateTransportError("not_found", 404)

    with pytest.raises(PrivateTransportError):
        next(stream(read, authorize))


def test_each_chunk_is_bounded_and_next_chunk_requires_current_policy():
    calls = []
    allowed = [True]

    def read(*args, **kwargs):
        calls.append(kwargs)
        return b"x"*kwargs["length"]

    def authorize():
        if not allowed[0]:
            raise PrivateTransportError("not_found", 404)

    iterator = stream(read, authorize, size=MAX_CHUNK_BYTES+1)
    assert len(next(iterator)) == MAX_CHUNK_BYTES
    allowed[0] = False
    with pytest.raises(PrivateTransportError):
        next(iterator)
    assert len(calls) == 1


@pytest.mark.parametrize("reader", [lambda *a, **k: b"", lambda *a, **k: b"too much"])
def test_missing_or_changed_object_is_not_partial_success(reader):
    with pytest.raises(PrivateTransportError) as exc:
        list(stream(reader))
    assert exc.value.code == "storage_unavailable"
