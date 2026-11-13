"""Exact HTTPS framing origins are separate from credentialed CORS origins."""

from django.utils.translation import gettext
from urllib.parse import urlsplit

from rest_framework.exceptions import ValidationError


def validate_origins(value):
    if not isinstance(value, list) or len(value) > 20:
        raise ValidationError(gettext("Use at most twenty exact HTTPS origins."))
    result = []
    for raw in value:
        if not isinstance(raw, str) or len(raw) > 255 or any(c in raw for c in "\r\n\t *'\"\\"):
            raise ValidationError(gettext("Use exact HTTPS origins without paths or wildcards."))
        try:
            parsed = urlsplit(raw)
            port = parsed.port
            host = parsed.hostname
        except ValueError as exc:
            raise ValidationError(gettext("Invalid HTTPS origin.")) from exc
        if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or raw.endswith(":")
                or not all(c.isascii() and (c.isalnum() or c in ".-:[]") for c in parsed.netloc)):
            raise ValidationError(gettext("Use exact HTTPS origins without paths or credentials."))
        canonical = f"https://{host.lower()}" + (f":{port}" if port and port != 443 else "")
        if raw != canonical:
            raise ValidationError(gettext("Use a lowercase canonical HTTPS origin without a default port."))
        if canonical not in result:
            result.append(canonical)
    return result
