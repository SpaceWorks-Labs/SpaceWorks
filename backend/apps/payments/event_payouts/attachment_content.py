"""Bounded receipt decoder and optional fail-closed ClamAV INSTREAM."""
from dataclasses import dataclass
from io import BytesIO
import re
import socket
import struct
import warnings


class ContentError(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


@dataclass(frozen=True)
class ScanResult:
    status: str
    version: str


def validate(data, *, declared_mime, purpose):
    if not isinstance(data, bytes) or not 0 < len(data) <= 10 * 1024 ** 2:
        raise ContentError("file_too_large", 413)
    if data.startswith(b"%PDF-"):
        actual = "application/pdf"
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
                raise ValueError()
            # Force page-tree parsing, bounded by byte/page limits.
            for page in reader.pages:
                if float(page.mediabox.width) <= 0 or float(page.mediabox.height) <= 0:
                    raise ValueError()
        except ImportError:
            raise ContentError("file_decoder_unavailable", 503) from None
        except Exception:
            raise ContentError("file_content_invalid") from None
    else:
        try:
            from PIL import Image
            heic = len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"hevx", b"mif1")
            if heic:
                if purpose != "reimbursement_receipt":
                    raise ContentError("file_type_unsupported")
                from pillow_heif import register_heif_opener
                register_heif_opener()
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    if (image.format not in ("JPEG", "PNG", "HEIF") or getattr(image, "n_frames", 1) != 1
                            or image.width * image.height > 25_000_000 or max(image.size) > 10000):
                        raise ValueError()
                    actual = {"JPEG": "image/jpeg", "PNG": "image/png", "HEIF": "image/heic"}[image.format]
                    image.verify()
                with Image.open(BytesIO(data)) as image:
                    image.load()
        except ContentError:
            raise
        except ImportError:
            raise ContentError("file_decoder_unavailable", 503) from None
        except Exception:
            raise ContentError("file_content_invalid") from None
    if actual != declared_mime:
        raise ContentError("file_mime_mismatch")
    return actual


def _reply(sock):
    result = bytearray()
    while b"\0" not in result and len(result) < 4096:
        chunk = sock.recv(512)
        if not chunk:
            break
        result.extend(chunk)
    if not result.endswith(b"\0") or len(result) > 4096:
        raise ContentError("scanner_unavailable", 503)
    return bytes(result[:-1])


def scan(data, *, backend, host=None, port=3310, connect=None):
    if backend == "none":
        return ScanResult("skipped", "policy-none-v1")
    if backend != "clamav" or not host:
        raise ContentError("scanner_unavailable", 503)
    connector = connect or socket.create_connection
    try:
        with connector((host, port), timeout=2) as sock:
            sock.settimeout(2)
            sock.sendall(b"zVERSION\0")
            match = re.match(br"ClamAV ([0-9.]{1,24})/([0-9]{1,16})(?:/|$)", _reply(sock))
            if match is None:
                raise ContentError("scanner_unavailable", 503)
            version = b"/".join(match.groups()).decode("ascii")
        with connector((host, port), timeout=2) as sock:
            sock.settimeout(2)
            sock.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), 65536):
                chunk = data[start:start + 65536]
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(b"\0\0\0\0")
            result = _reply(sock)
            if result.endswith(b" FOUND"):
                return ScanResult("infected", version)
            if result != b"stream: OK":
                raise ContentError("scanner_unavailable", 503)
            return ScanResult("clean", version)
    except (OSError, TimeoutError):
        raise ContentError("scanner_unavailable", 503) from None
