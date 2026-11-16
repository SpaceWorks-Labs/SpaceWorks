"""The one bounded, pinned HTTP transport for calls to tenant-configured destinations.

``send`` dials the addresses ``apps.outbound_policy.resolve`` already validated (never the host name again),
keeps the original Host header and TLS server name (certificates are verified against the name, not the IP),
never follows redirects (a 3xx is returned to the caller, which treats it as a failure), ignores proxy
environment variables (``http.client`` has no proxy support), reads at most ``max_bytes`` of body and stops the
whole exchange at an overall ``deadline``: a watchdog closes the socket, so a peer that drips one byte at a
time (headers or body) cannot hold a worker for longer than that.

Failures are ``OutboundError`` with a short reason (``timeout``, ``unreachable``, ``too_large``); bodies,
headers and credentials never reach a log line.
"""
import http.client
import socket
import ssl
import threading
import time
from dataclasses import dataclass, field

CHUNK = 64 * 1024


class OutboundError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass
class Response:
    status: int
    headers: dict = field(default_factory=dict)  # lower-case names
    body: bytes = b""

    def header(self, name, default=""):
        return self.headers.get(name.lower(), default)

    @property
    def content_type(self):
        return self.header("content-type").split(";")[0].strip().lower()


class _PinnedMixin:
    _watch = None

    def _pinned_socket(self):
        address = self._pinned
        raw = socket.socket(address.family, socket.SOCK_STREAM)
        raw.settimeout(self.timeout)
        if self._watch is not None:  # the watchdog can abort a dripping TLS handshake too
            self._watch.sock = raw
        try:
            raw.connect(address.sockaddr)
        except BaseException:
            raw.close()
            raise
        return raw


class _PinnedHTTP(_PinnedMixin, http.client.HTTPConnection):
    def __init__(self, target, address, timeout):
        super().__init__(target.hostname, target.port, timeout=timeout)
        self._pinned = address

    def connect(self):
        self.sock = self._pinned_socket()


def _tls_context():
    """Certificate verification with the same CA bundle `requests`/`httpx` used before (certifi), else the system's."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, OSError):
        return ssl.create_default_context()


class _PinnedHTTPS(_PinnedMixin, http.client.HTTPSConnection):
    def __init__(self, target, address, timeout):
        super().__init__(target.hostname, target.port, timeout=timeout, context=_tls_context())
        self._pinned = address

    def connect(self):
        raw = self._pinned_socket()
        try:  # `self.host` is still the URL's host name: SNI and certificate checks use it, not the pinned IP
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class _Watchdog:
    """Shuts the socket when the overall deadline passes, which unblocks any read in progress."""

    def __init__(self, seconds):
        self.fired, self.sock = False, None
        self._timer = threading.Timer(max(seconds, 0.001), self._fire)
        self._timer.daemon = True

    def _fire(self):
        self.fired = True
        sock = self.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def __enter__(self):
        self._timer.start()
        return self

    def __exit__(self, *_exc):
        self._timer.cancel()


def _read_body(response, max_bytes, deadline, truncate=False):
    chunks, total = [], 0
    while True:
        if time.monotonic() >= deadline:
            raise OutboundError("timeout")
        chunk = response.read1(min(CHUNK, max_bytes + 1 - total))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            if truncate:  # the caller only needs the status: stop reading, keep what fits
                chunks.append(chunk)
                return b"".join(chunks)[:max_bytes]
            raise OutboundError("too_large")
        chunks.append(chunk)


def _exchange(target, address, method, body, headers, *, connect_timeout, read_timeout, deadline, max_bytes,
              truncate):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise OutboundError("timeout")
    kind = _PinnedHTTPS if target.scheme == "https" else _PinnedHTTP
    connection = kind(target, address, timeout=min(connect_timeout, remaining))
    with _Watchdog(remaining) as watchdog:
        connection._watch = watchdog
        try:
            connection.connect()
        except (socket.timeout, TimeoutError):
            connection.close()
            raise OutboundError("connect_timeout") from None
        except (OSError, ValueError):
            connection.close()
            raise OutboundError("connect_failed") from None
        try:
            watchdog.sock = connection.sock
            connection.sock.settimeout(min(read_timeout, max(deadline - time.monotonic(), 0.001)))
            connection.request(method, target.request_target, body=body,
                               headers={**(headers or {}), "Host": target.host_header})
            response = connection.getresponse()
            data = b"" if method == "HEAD" else _read_body(response, max_bytes, deadline, truncate)
            if watchdog.fired:  # the shutdown reads as a clean EOF (read1 returns b""): a cut body is not an answer
                raise OutboundError("timeout")
            return Response(response.status, {k.lower(): v for k, v in response.getheaders()}, data)
        except OutboundError:
            raise
        except (socket.timeout, TimeoutError):
            raise OutboundError("timeout") from None
        except (OSError, http.client.HTTPException, ssl.SSLError, ValueError):
            raise OutboundError("timeout" if watchdog.fired else "unreachable") from None
        finally:
            connection.close()


def send(target, method, *, body=None, headers=None, max_bytes, connect_timeout=4, read_timeout=10, deadline=20,
         truncate=False):
    """One request to a pinned ``Target`` -> ``Response``. Tries the next validated address only when the
    previous one could not be CONNECTED to; once a request was written it is never replayed elsewhere.
    ``truncate=True`` stops reading at ``max_bytes`` instead of failing (for callers that need only the status)."""
    stop = time.monotonic() + deadline
    last = OutboundError("unreachable")
    for address in target.addresses:
        try:
            return _exchange(target, address, method, body, headers, connect_timeout=connect_timeout,
                             read_timeout=read_timeout, deadline=stop, max_bytes=max_bytes, truncate=truncate)
        except OutboundError as exc:
            if exc.reason not in ("connect_failed", "connect_timeout"):
                raise
            last = OutboundError("timeout" if exc.reason == "connect_timeout" else "unreachable")
    raise last
