"""Optional clamd INSTREAM, explicit skip policy and fail-closed configured errors."""
from dataclasses import dataclass
import socket
import struct
import re

from .errors import SubmissionError


@dataclass(frozen=True)
class ScanResult:
    backend: str
    status: str
    version: str


def scan(reader, *, backend, host=None, port=3310, max_scan_bytes=2 * 1024 ** 3, connect=None):
    if backend == "none":
        return ScanResult("none", "skipped", "policy-none-v1")
    if backend != "clamav" or not host:
        raise SubmissionError("scanner_unavailable", 503)
    if reader.size > max_scan_bytes:
        raise SubmissionError("scan_limit", 413)
    connector = connect or socket.create_connection
    try:
        with connector((host, port), timeout=5) as version_socket:
            version_socket.settimeout(5)
            version_socket.sendall(b"zVERSION\0")
            match = re.match(br"ClamAV ([0-9.]{1,24})/([0-9]{1,16})(?:/|$)", _reply(version_socket))
            if match is None:
                raise SubmissionError("scanner_unavailable", 503)
            version = b"/".join(match.groups()).decode("ascii")
        with connector((host, port), timeout=5) as sock:
            sock.settimeout(5)
            sock.sendall(b"zINSTREAM\0")
            for chunk in reader.chunks(65536):
                sock.sendall(struct.pack("!I", len(chunk)))
                sock.sendall(chunk)
            sock.sendall(b"\0\0\0\0")
            status = _reply(sock)
            if status.endswith(b" FOUND"):
                return ScanResult("clamav", "infected", version)
            if status != b"stream: OK":
                raise SubmissionError("scanner_incomplete", 503)
    except (OSError, TimeoutError) as exc:
        raise SubmissionError("scanner_unavailable", 503) from exc
    return ScanResult("clamav", "clean", version)


def _reply(sock):
    result = bytearray()
    while b"\0" not in result and len(result) < 4096:
        chunk = sock.recv(512)
        if not chunk:
            break
        result.extend(chunk)
    if not result.endswith(b"\0") or len(result) > 4096:
        raise SubmissionError("scanner_incomplete", 503)
    return bytes(result[:-1])
