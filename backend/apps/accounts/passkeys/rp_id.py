"""The relying-party ID: derived only from an origin this deployment verifiably serves.

A ceremony's origin is the request's ``Origin`` header, and it must be EXACTLY one of:
``PUBLIC_APP_BASE_URL``, an entry of ``PLATFORM_STAFF_ORIGINS``, or
``https://<frontend_domain>`` of a makerspace whose custom domain is verified. The RP ID
is that origin's host, except under ``PLATFORM_DOMAIN_SUFFIX`` (managed hosting), where
it is the suffix without its dot, so one passkey works on every space subdomain.

An RP ID is refused when it is an IP address or a public suffix (the bundled Public
Suffix List snapshot, private domains included, never fetched over the network): a
passkey scoped to ``github.io`` or ``co.uk`` would be usable by unrelated sites.
"""

import ipaddress
from functools import lru_cache
from urllib.parse import urlsplit

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.accounts.login_security_contract import RP_ID_UNAVAILABLE


class RpIdUnavailable(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = RP_ID_UNAVAILABLE

    def __init__(self, detail="Passkeys are not available on this address."):
        super().__init__({"detail": detail, "code": RP_ID_UNAVAILABLE})


@lru_cache(maxsize=1)
def _extractor():
    import tldextract
    # No network, no cache directory: only the snapshot shipped inside the package.
    return tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, fallback_to_snapshot=True,
                                 include_psl_private_domains=True)


def normalize_origin(raw):
    """``scheme://host[:port]`` in lower case, or "" when it is not an origin."""
    parts = urlsplit(str(raw or "").strip())
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.path not in ("", "/"):
        return ""
    if parts.query or parts.fragment or parts.username or parts.password:
        return ""
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname.lower()}{port}"


def is_public_suffix(host):
    host = (host or "").strip(".").lower()
    if not host:
        return True
    result = _extractor()(host)
    return bool(result.suffix) and not result.domain


def _is_ip(host):
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def validate_rp_id(rp_id):
    """Refuse an RP ID no passkey may be scoped to; return it unchanged otherwise."""
    if not rp_id or _is_ip(rp_id) or is_public_suffix(rp_id):
        raise RpIdUnavailable()
    return rp_id


def _static_origins():
    origins = {normalize_origin(settings.PUBLIC_APP_BASE_URL)} if settings.PUBLIC_APP_BASE_URL else set()
    origins |= {normalize_origin(origin) for origin in settings.PLATFORM_STAFF_ORIGINS}
    return {origin for origin in origins if origin}


def _verified_custom_origin(origin):
    parts = urlsplit(origin)
    if parts.scheme != "https" or parts.port:
        return False
    from apps.makerspaces.models import Makerspace
    return Makerspace.objects.filter(
        frontend_domain__iexact=parts.hostname, frontend_domain_status=Makerspace.DomainStatus.VERIFIED,
    ).exists()


def is_trusted_origin(origin):
    origin = normalize_origin(origin)
    return bool(origin) and (origin in _static_origins() or _verified_custom_origin(origin))


def rp_id_for_host(host):
    host = (host or "").lower()
    suffix = settings.PLATFORM_DOMAIN_SUFFIX or ""
    if suffix and (host == suffix.lstrip(".") or host.endswith(suffix)):
        return suffix.lstrip(".")
    return host


def rp_id_for_origin(origin):
    """The RP ID for a trusted origin; ``RpIdUnavailable`` for anything else."""
    origin = normalize_origin(origin)
    if not is_trusted_origin(origin):
        raise RpIdUnavailable()
    return validate_rp_id(rp_id_for_host(urlsplit(origin).hostname))


def request_origin_and_rp_id(request):
    """``(origin, rp_id)`` of a ceremony request, from its ``Origin`` header only."""
    origin = normalize_origin(request.headers.get("Origin", ""))
    return origin, rp_id_for_origin(origin)


def configured_rp_ids():
    """Every RP ID the static configuration yields (the system check validates them)."""
    return {rp_id_for_host(urlsplit(origin).hostname) for origin in _static_origins()}
