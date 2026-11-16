"""Normalize HTTPS links without fetching, DNS, unfurls or arbitrary iframes."""
import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from .errors import SubmissionError

KINDS = {"repo", "demo", "video", "slides", "cad", "pcb", "firmware", "other"}
PROVIDERS = {
    "youtube.com": "youtube", "youtu.be": "youtube", "vimeo.com": "vimeo", "loom.com": "loom",
    "drive.google.com": "google", "docs.google.com": "google", "slides.google.com": "google",
    "canva.com": "canva", "figma.com": "figma", "github.com": "github", "gitlab.com": "gitlab",
    "oshwlab.com": "oshwlab", "365.altium.com": "altium", "cad.onshape.com": "onshape",
    "a360.co": "fusion", "sketchfab.com": "sketchfab", "printables.com": "printables",
    "kicanvas.org": "kicanvas",
}


def normalize_link(value, kind):
    if kind not in KINDS or not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise SubmissionError("invalid_link")
    if (any(unicodedata.category(c).startswith("C") or c.isspace() for c in value) or
            "\\" in value or re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", value, re.I)):
        raise SubmissionError("invalid_link")
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() != "https" or parts.username is not None or parts.password is not None:
            raise ValueError()
        host = (parts.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
        if not host or parts.port not in (None, 443) or host == "localhost" or host.endswith(".local"):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or not re.fullmatch(r"[a-z0-9.-]+", host):
                raise ValueError()
        else:
            if not address.is_global:
                raise ValueError()
            host = f"[{host}]" if address.version == 6 else host
        normalized = urlunsplit(("https", host, parts.path or "/", parts.query, parts.fragment))
    except (ValueError, UnicodeError) as exc:
        raise SubmissionError("invalid_link") from exc
    return normalized, PROVIDERS.get(host.removeprefix("www."), "external")
