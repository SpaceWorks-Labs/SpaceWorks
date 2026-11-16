"""Provider verification uses configured public URLs, never forwarded headers."""
import base64
import hashlib
import hmac
from urllib.parse import urlsplit, urlunsplit

from .resolver import webhook_base


def twilio_url_variants(url):
    parsed = urlsplit(url)
    port = parsed.port
    host = parsed.netloc
    if port is not None:
        host = host[:host.index("]") + 1] if host.startswith("[") else host.rsplit(":", 1)[0]
    default = 443 if parsed.scheme == "https" else 80
    # RequestValidator checks with and without the port, including explicit ports.
    without = urlunsplit(parsed._replace(netloc=host))
    with_port = urlunsplit(parsed._replace(netloc=f"{host}:{port if port is not None else default}"))
    return {url, without, with_port}


def twilio_signature(token, url, params):
    value = url
    for name in sorted(set(params)):
        values = params.getlist(name) if hasattr(params, "getlist") else [params[name]]
        for item in sorted(set(values)):
            value += name + item
    return base64.b64encode(hmac.new(token.encode(), value.encode(), hashlib.sha1).digest()).decode()


def verify_twilio(request, secret):
    base = webhook_base()
    if not base:
        return False
    # The public deployment prefix belongs to the configured base, not SCRIPT_NAME twice.
    url = base + request.path_info
    query = request.META.get("QUERY_STRING", "")
    if query:
        url += "?" + query
    signature = request.headers.get("X-Twilio-Signature", "")
    return any(hmac.compare_digest(twilio_signature(secret, variant, request.data).encode(), signature.encode())
               for variant in twilio_url_variants(url))


def verify_meta(body, secret, signature):
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), signature.encode())
