"""A public Google Sheet as an import source (L13; #74, #128 C-12/C-13).

Staff paste a sheet's share link instead of uploading a file. The link is turned into
the sheet's CSV export URL, fetched once per request, and the bytes are handed to the
SAME parser and planner an uploaded CSV goes through -- there is no second importer.

The fetch is a fail-safe outbound call:

* only `https://docs.google.com/spreadsheets/...` links are accepted, and a redirect is
  followed only to `docs.google.com` or `*.googleusercontent.com` (where Google serves
  the export) -- a redirect to Google's sign-in page means the sheet is not public;
* every hop's host is resolved first and refused unless every address is public, and
  the connection is pinned to the checked address (TLS still verifies the real name);
* HTTPS only, connect/read timeouts and an overall deadline, a byte cap equal to the
  importer's upload cap and a row cap; no cookies, no credentials, no proxy or netrc
  from the environment, no OAuth -- public sheets only;
* failures are logged without the URL (a sheet id is a capability) and surface as typed
  400s: `sheet_url_invalid`, `sheet_not_public`, `sheet_too_large`, `sheet_changed`,
  or a 502 `sheet_unreachable`.

Nothing is stored: the bytes live for the request, like an uploaded file.
"""
import csv
import hashlib
import io
import logging
import re
import socket
import time
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import parse_qs, urljoin, urlsplit

from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

SOURCE_FILE, SOURCE_SHEET = "file", "google_sheet"
SHEET_HOST = "docs.google.com"
_EXPORT_SUFFIX = ".googleusercontent.com"
_SIGN_IN_HOSTS = ("accounts.google.com",)
_PATH = re.compile(r"^/spreadsheets/(?:u/\d{1,2}/)?d/(?:(e)/)?([A-Za-z0-9_-]{20,200})(?:/[^?#]*)?$")
_GID = re.compile(r"^\d{1,12}$")
CONNECT_SECONDS, READ_SECONDS, DEADLINE_SECONDS, MAX_REDIRECTS = 5.0, 15.0, 30.0, 5
MESSAGES = {
    "sheet_url_invalid": "Paste the share link of a Google Sheet (https://docs.google.com/spreadsheets/d/…).",
    "sheet_not_public": "SpaceWorks could not open this sheet. In Google Sheets choose Share, set General "
                        "access to “Anyone with the link” (Viewer), then try again.",
    "sheet_too_large": "The sheet is larger than this import allows.",
    "sheet_unreachable": "Google Sheets did not answer. Try again in a minute.",
    "sheet_changed": "The sheet changed after the preview. Preview it again before importing.",
}


class SheetImportError(APIException):
    status_code = 400

    def __init__(self, code, detail=None):
        self.code = code
        if code == "sheet_unreachable":
            self.status_code = 502
        super().__init__({"code": code, "detail": detail or MESSAGES[code]})


def _fail(code, reason, **extra):
    # Structured, URL-free: the host and a reason are enough to diagnose.
    logger.warning("sheet_import_fetch_failed", extra={"code": code, "reason": reason, **extra})
    return SheetImportError(code)


def export_url(raw):
    """A share/edit/published link -> its CSV export URL, or `sheet_url_invalid`."""
    value = (raw or "").strip()
    if not value or len(value) > 2048 or any(char.isspace() or char == "\\" for char in value):
        raise SheetImportError("sheet_url_invalid")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise SheetImportError("sheet_url_invalid") from None
    match = _PATH.match(parts.path or "")
    if (parts.scheme != "https" or parts.hostname != SHEET_HOST or port not in (None, 443)
            or parts.username or parts.password or not match):
        raise SheetImportError("sheet_url_invalid")
    gids = parse_qs(parts.query).get("gid", []) + parse_qs(parts.fragment).get("gid", [])
    gid = gids[0] if gids else ""
    if gid and not _GID.match(gid):
        raise SheetImportError("sheet_url_invalid")
    published, sheet_id = match.groups()
    if published:  # File > Share > Publish to web
        query = f"output=csv{f'&gid={gid}&single=true' if gid else ''}"
        return f"https://{SHEET_HOST}/spreadsheets/d/e/{sheet_id}/pub?{query}"
    return f"https://{SHEET_HOST}/spreadsheets/d/{sheet_id}/export?format=csv{f'&gid={gid}' if gid else ''}"


def _getaddrinfo(host):
    return socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)


def _public_address(host):
    """Resolve `host`; every answer must be a public address. Returns the one to pin."""
    try:
        answers = _getaddrinfo(host)
    except (OSError, UnicodeError):
        raise _fail("sheet_unreachable", "dns_failed", host=host) from None
    addresses = []
    for family, _type, _proto, _name, sockaddr in answers:
        address = ip_address(str(sockaddr[0]).split("%", 1)[0])
        address = getattr(address, "ipv4_mapped", None) or address
        if family not in (socket.AF_INET, socket.AF_INET6) or not address.is_global:
            raise _fail("sheet_unreachable", "private_address", host=host)
        addresses.append(address)
    if not addresses:
        raise _fail("sheet_unreachable", "dns_empty", host=host)
    return addresses[0]


def _allowed(parts):
    host = parts.hostname or ""
    try:
        port = parts.port
    except ValueError:
        return False
    return (parts.scheme == "https" and port in (None, 443) and not parts.username and not parts.password
            and (host == SHEET_HOST or host.endswith(_EXPORT_SUFFIX)))


@dataclass(frozen=True)
class SheetFetch:
    content: bytes
    sha256: str

    def as_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile("google-sheet.csv", self.content, content_type="text/csv")

    def response_fields(self):
        return {"source": SOURCE_SHEET, "sheet_sha256": self.sha256}


def _read(response, max_bytes, started):
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > max_bytes:
        raise _fail("sheet_too_large", "declared_length")
    chunks, size = [], 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > max_bytes:
            raise _fail("sheet_too_large", "bytes")
        if time.monotonic() - started > DEADLINE_SECONDS:
            raise _fail("sheet_unreachable", "deadline")
        chunks.append(chunk)
    return b"".join(chunks)


def _count_rows(content, max_rows):
    text = content.decode("utf-8-sig", errors="replace")
    rows = sum(1 for row in csv.reader(io.StringIO(text, newline="")) if any(cell.strip() for cell in row))
    if rows - 1 > max_rows:  # the first row is the header
        raise _fail("sheet_too_large", "rows")


def fetch_sheet(url, *, max_bytes, max_rows, transport=None):
    """Fetch a public sheet's CSV export under every guard above."""
    import httpx
    target, started = export_url(url), time.monotonic()
    timeout = httpx.Timeout(READ_SECONDS, connect=CONNECT_SECONDS)
    with httpx.Client(transport=transport, timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            parts = urlsplit(target)
            address = _public_address(parts.hostname)
            netloc = f"[{address}]" if address.version == 6 else str(address)
            pinned = parts._replace(netloc=netloc).geturl()
            client.cookies.clear()
            headers = {"Host": parts.hostname, "Accept": "text/csv", "User-Agent": "SpaceWorks-Sheet-Import/1"}
            try:
                with client.stream("GET", pinned, headers=headers,
                                   extensions={"sni_hostname": parts.hostname}) as response:
                    if response.is_redirect:
                        target = urljoin(target, response.headers.get("location", ""))
                        landing = urlsplit(target)
                        if landing.hostname in _SIGN_IN_HOSTS:
                            raise _fail("sheet_not_public", "sign_in_redirect")
                        if not _allowed(landing):
                            raise _fail("sheet_unreachable", "redirect_refused", host=landing.hostname or "")
                        continue
                    if response.status_code in (401, 403, 404):
                        raise _fail("sheet_not_public", "status", status=response.status_code)
                    if response.status_code != 200:
                        raise _fail("sheet_unreachable", "status", status=response.status_code)
                    if "html" in response.headers.get("content-type", "").lower():
                        raise _fail("sheet_not_public", "html_page")
                    content = _read(response, max_bytes, started)
            except httpx.TimeoutException:
                raise _fail("sheet_unreachable", "timeout", host=parts.hostname) from None
            except httpx.HTTPError:
                raise _fail("sheet_unreachable", "transport", host=parts.hostname) from None
            _count_rows(content, max_rows)
            return SheetFetch(content, hashlib.sha256(content).hexdigest())
    raise _fail("sheet_unreachable", "too_many_redirects")
