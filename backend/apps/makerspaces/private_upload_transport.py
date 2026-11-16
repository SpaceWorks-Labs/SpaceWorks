"""Always-present, model-free private upload and bounded streaming primitives.

Subject adapters own authorization, audit, quotas, storage clients and lifecycle.
No Events imports, redirect/presign download shortcut, positive policy cache or
DB transaction belongs here. Locators passed to readers are server-owned only.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from typing import Callable, Iterator, Mapping, Protocol

MAX_CHUNK_BYTES = 1_048_576
MAX_POLICY_INTERVAL_SECONDS = 2


class PrivateTransportError(Exception):
    def __init__(self, code: str, status: int):
        self.code, self.status = code, status
        super().__init__(code)


@dataclass(frozen=True, kw_only=True)
class ObjectLocator:
    bucket: str
    key: str = field(repr=False)
    version_id: str | None = field(default=None, repr=False)


@dataclass(frozen=True, kw_only=True)
class UploadDescriptor:
    method: str
    url: str = field(repr=False)
    fields: Mapping[str, str] = field(repr=False)
    expires_at: datetime
    generation: int


@dataclass(frozen=True, kw_only=True)
class UploadRequest:
    staging: ObjectLocator
    generation: int
    mime: str
    size_bytes: int
    not_after: datetime


class UploadTransport(Protocol):
    def initialize(self, request: UploadRequest) -> UploadDescriptor:
        """Exact MIME/size binding; stage only, never presign a final key."""
        ...

    def abort(self, *, staging: ObjectLocator, upload_id: str | None) -> None: ...

    def copy_verified(
        self, *, source: ObjectLocator, target: ObjectLocator, sha256: str,
    ) -> ObjectLocator:
        """Conditional immutable copy of a server-verified exact object version."""
        ...


class RangeReader(Protocol):
    def __call__(
        self, locator: ObjectLocator, *, start: int, length: int, timeout_seconds: int,
    ) -> bytes:
        """Bound SDK request timeout; return exactly the requested bytes."""
        ...


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int
    total: int
    partial: bool

    @property
    def length(self):
        return self.end - self.start + 1

    @property
    def content_range(self):
        return f"bytes {self.start}-{self.end}/{self.total}"


def resolve_range(header: str | None, size_bytes: int) -> ByteRange:
    """One RFC byte range only. HTTP adapters add Content-Range: bytes */size on 416."""
    if type(size_bytes) is not int or size_bytes < 0:
        raise ValueError("Invalid server object size.")
    if header is None:
        return ByteRange(0, size_bytes - 1, size_bytes, False)
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header) if isinstance(header, str) else None
    if not match or not any(match.groups()) or size_bytes == 0:
        raise PrivateTransportError("invalid_range", 416)
    left, right = match.groups()
    # Bound attacker-supplied integers before int conversion.
    if len(left) > 20 or len(right) > 20:
        raise PrivateTransportError("invalid_range", 416)
    if not left:
        suffix = int(right)
        if suffix == 0:
            raise PrivateTransportError("invalid_range", 416)
        start, end = max(0, size_bytes - suffix), size_bytes - 1
    else:
        start = int(left)
        end = min(int(right), size_bytes - 1) if right else size_bytes - 1
    if start >= size_bytes or start > end:
        raise PrivateTransportError("invalid_range", 416)
    return ByteRange(start, end, size_bytes, True)


def _aware(value: datetime):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Use timezone-aware deadlines.")
    return value


def bounded_not_after(
    *, now: datetime, purpose_max_seconds: int, limits: tuple[datetime | None, ...] = (),
) -> datetime:
    """Floor TTL, taking every applicable object/authority/session deadline."""
    _aware(now)
    if type(purpose_max_seconds) is not int or purpose_max_seconds <= 0:
        raise ValueError("A positive purpose TTL is required.")
    deadline = min([now + timedelta(seconds=purpose_max_seconds)] + [
        _aware(limit) for limit in limits if limit is not None
    ])
    seconds = int((deadline - now).total_seconds())
    if seconds <= 0:
        raise PrivateTransportError("asset_expired", 410)
    return now + timedelta(seconds=seconds)


def stream_private(
    *, locator: ObjectLocator, byte_range: ByteRange, reader: RangeReader,
    authorize: Callable[[], None], clock: Callable[[], datetime], not_after: datetime,
) -> Iterator[bytes]:
    """Policy recheck before read and before release of each ≤1 MiB chunk.

    HTTP adapters authorize before constructing headers too, including HEAD.
    An already authorized response cannot change HTTP status after it starts;
    subsequent refusal terminates it. Reader must honor its two-second timeout.
    """
    _aware(not_after)

    def check():
        authorize()
        if _aware(clock()) >= not_after:
            raise PrivateTransportError("asset_expired", 410)

    check()  # Empty streams still authorize; expired bytes never touch storage.
    offset = byte_range.start
    while offset <= byte_range.end:
        check()
        length = min(MAX_CHUNK_BYTES, byte_range.end - offset + 1)
        try:
            chunk = reader(locator, start=offset, length=length,
                           timeout_seconds=MAX_POLICY_INTERVAL_SECONDS)
        except PrivateTransportError:
            raise
        except Exception as exc:
            raise PrivateTransportError("storage_unavailable", 503) from exc
        check()  # Hold this chunk until current live authority is proved again.
        if not isinstance(chunk, bytes) or len(chunk) != length:
            raise PrivateTransportError("storage_unavailable", 503)
        offset += length
        yield chunk
