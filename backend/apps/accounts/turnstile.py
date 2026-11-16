"""Optional Cloudflare Turnstile on sign-in (#62: shown after failures, off until keys).

Active for a request only when BOTH keys are set AND the request comes from an origin this
deployment verifiably serves (``passkeys.rp_id.is_trusted_origin``: the app URL, a platform
staff origin, or a space's verified custom domain) whose host is in ``TURNSTILE_HOSTNAMES``
(empty: that origin's own host). Everything else is never asked for a token, so a native
app (attestation is its proof) and an unconfigured deployment behave exactly as before.

When it is active, a token is required on the CAPTCHA routes (``CAPTCHA_ROUTES``: password
sign-in, sign-up, password reset and emailed-code requests):
- after ``TURNSTILE_AFTER_FAILURES`` failures from the source or for the account
  (the platform rule whenever Turnstile is on);
- always, on a space's verified custom domain whose ``security.captcha_on_sign_in`` is
  ``always`` (the space can only tighten the platform rule);
- instead of the 429, for a source under an automatic block (never a deny rule).

The browser sends the token in the ``X-Turnstile-Token`` header (or the
``cf-turnstile-response`` form field). It is checked server-side with ``siteverify``
(3 s): ``success``, the expected ``action`` and ``hostname``. When Cloudflare cannot be
reached ``TURNSTILE_FAIL_MODE=open`` (default) lets the request through.
"""

import logging
from urllib.parse import urlsplit

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TIMEOUT_SECONDS = 3
TOKEN_HEADER = "X-Turnstile-Token"
TOKEN_FIELD = "cf-turnstile-response"
OK, MISSING, INVALID, UNAVAILABLE = "ok", "missing", "invalid", "unavailable"
# Route name -> the widget action the token must carry.
CAPTCHA_ROUTES = {
    "auth-login": "login",
    "auth-member-sign-up": "signup",
    "auth-forgot-password": "reset",
    "auth-reset-password": "reset",
    "auth-phone-login-start": "code",
    "auth-email-verification-resend": "code",
    "auth-account-merge-start": "code",
    "auth-login-code-resend": "code",  # S-B
}


def configured():
    return bool(settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY)


def verified_host(request):
    """The host of the request's Origin when this deployment verifiably serves it, else ""."""
    from apps.accounts.passkeys.rp_id import is_trusted_origin, normalize_origin

    origin = normalize_origin(request.headers.get("Origin", ""))
    if not origin or not is_trusted_origin(origin):
        return ""
    return urlsplit(origin).hostname or ""


def active_host(request):
    """The verified host Turnstile runs on for this request, or "" when it is not active."""
    if not configured():
        return ""
    host = verified_host(request)
    allowed = {name.strip().lower() for name in settings.TURNSTILE_HOSTNAMES if name.strip()}
    if not host or (allowed and host not in allowed):
        return ""
    return host


def space_mode(host):
    """``security.captcha_on_sign_in`` of the space whose VERIFIED custom domain is ``host``."""
    from apps.accounts.login_security_contract import CAPTCHA_ON_SIGN_IN
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.security_settings_person import space_value

    space = Makerspace.objects.filter(
        frontend_domain__iexact=host, frontend_domain_status=Makerspace.DomainStatus.VERIFIED).first()
    if space is None:
        return "off"
    try:
        return space_value(space, CAPTCHA_ON_SIGN_IN)
    except Exception:
        logger.warning("captcha_policy_unreadable", exc_info=True)
        return "off"


def token(request):
    value = request.headers.get(TOKEN_HEADER) or ""
    if not value and request.content_type in ("application/x-www-form-urlencoded", "multipart/form-data"):
        value = request.POST.get(TOKEN_FIELD, "")
    return value.strip()[:2048]


def _transport():
    """Tests replace this with an ``httpx.MockTransport``; production uses the network."""
    return None


def verify(request, action, host, remote_ip):
    """``OK``, ``MISSING``, ``INVALID`` or ``UNAVAILABLE`` for this request's token."""
    value = token(request)
    if not value:
        return MISSING
    data = {"secret": settings.TURNSTILE_SECRET_KEY, "response": value}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, transport=_transport()) as client:
            response = client.post(SITEVERIFY_URL, data=data)
        body = response.json() if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        body = None
    if body is None:
        logger.warning("turnstile_unavailable")
        return UNAVAILABLE
    if not isinstance(body, dict) or body.get("success") is not True:
        return INVALID
    if body.get("action") != action or str(body.get("hostname", "")).lower() != host:
        return INVALID
    return OK
