"""``LoginIPGuardMiddleware``: platform IP rules, automatic blocks and Turnstile at the doors.

It acts only on sign-in-family views (a view class with ``login_ip_guard = True``, plus
``GUARDED_ROUTES`` for views this lane may not edit and the ``/control/`` login page), and
never on OPTIONS. Order of decisions for one request:

1. an ALLOW rule covering the client: no IP refusal at all;
2. a DENY rule: 429 ``ip_blocked`` (``Retry-After`` when the rule expires);
3. an automatic block, unless a remembered device bypasses it: on a CAPTCHA route where
   Turnstile is active, a valid token lets it through (``captcha_required`` /
   ``captcha_failed`` otherwise); elsewhere 429 ``ip_blocked`` with ``Retry-After``;
4. Turnstile's own rule on CAPTCHA routes (after failures, or a space's ``always``).

It sits before ``AxesMiddleware`` so a refused request never reaches a credential check.
"""

import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from apps.accounts import ip_guard, ip_rules, turnstile
from apps.accounts.login_security_contract import CAPTCHA_FAILED, CAPTCHA_REQUIRED, IP_ALLOW, IP_BLOCKED, IP_DENY

logger = logging.getLogger(__name__)
ADMIN_LOGIN = "admin:login"
# Sign-in routes whose views belong to lanes that must not be edited here (passkeys: S-A).
GUARDED_ROUTES = frozenset({
    ADMIN_LOGIN, "auth-passkeys-authenticate-options", "auth-passkeys-authenticate-verify",
    "auth-mfa-passkey-options",
})
_UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_BODY_LIMIT = 16 * 1024
_IDENTIFIER_FIELDS = ("username", "email", "identifier", "phone")


def guarded(view_func, route):
    cls = getattr(view_func, "cls", None) or getattr(view_func, "view_class", None)
    return bool(getattr(cls, "login_ip_guard", False) or getattr(view_func, "login_ip_guard", False)
                or route in GUARDED_ROUTES)


def _identifier(request):
    """The account a CAPTCHA-route body names (for the per-account failure count)."""
    if request.content_type != "application/json":
        return request.POST.get("username", "") if request.method == "POST" else ""
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > _BODY_LIMIT:
            return ""
        payload = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return next((str(payload[name]) for name in _IDENTIFIER_FIELDS if isinstance(payload.get(name), str)), "")


def _blocked(route, retry_after):
    if route == ADMIN_LOGIN:
        response = HttpResponse("Too many failed sign-ins from this network. Try again later.",
                                status=429, content_type="text/plain")
    else:
        response = JsonResponse({"detail": "Too many failed sign-ins from your network. Try again later.",
                                 "code": IP_BLOCKED}, status=429)
    if retry_after:
        response["Retry-After"] = str(int(retry_after))
    return response


def _captcha_refusal(code, action):
    detail = ("Complete the CAPTCHA to continue." if code == CAPTCHA_REQUIRED
              else "The CAPTCHA could not be verified. Try again.")
    return JsonResponse({"detail": detail, "code": code, "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
                         "turnstile_action": action}, status=400)


def _audit_captcha_failure(source):
    from apps.audit import services as audit

    key = source.key or "unknown"
    try:  # one row per source per window, so garbage tokens cannot flood the audit log
        if not cache.add(f"sec:capaudit:{key}", 1, settings.LOGIN_IP_BLOCK_WINDOW_SECONDS):
            return
    except Exception:
        logger.warning("ip_guard_cache_unavailable", exc_info=True)
    audit.record(None, "auth.captcha_failed", target_type="accounts.ipautoblock", meta={"ip_key": key})


def _captcha(request, source, action, host):
    """None when the token passes (or Cloudflare is unreachable in open mode), else a 400."""
    result = turnstile.verify(request, action, host, str(source.address or ""))
    if result == turnstile.OK or (result == turnstile.UNAVAILABLE and settings.TURNSTILE_FAIL_MODE == "open"):
        return None
    if result == turnstile.MISSING:
        return _captcha_refusal(CAPTCHA_REQUIRED, action)
    _audit_captcha_failure(source)
    return _captcha_refusal(CAPTCHA_FAILED, action)


def _captcha_needed(request, source, host):
    mode = turnstile.space_mode(host)
    if mode == "always":
        return True
    return ip_guard.failures(source, _identifier(request)) >= settings.TURNSTILE_AFTER_FAILURES


class LoginIPGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        pending = getattr(request, ip_guard.PENDING_BLOCK, None)
        if pending is not None:
            try:
                ip_guard.block(pending)
            except Exception:
                logger.exception("ip_auto_block_failed")
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = getattr(request, "resolver_match", None)
        route = getattr(match, "view_name", None)
        if request.method == "OPTIONS" or not guarded(view_func, route):
            return None
        source = ip_guard.client_source(request)
        verdict, retry_after = ip_rules.decision(source.address)
        if verdict == IP_DENY:
            return _blocked(route, retry_after)
        action = turnstile.CAPTCHA_ROUTES.get(route)
        host = turnstile.active_host(request) if action and request.method in _UNSAFE else ""
        if verdict != IP_ALLOW:
            block = ip_guard.active_block(source)
            if block is not None and not ip_guard.device_bypasses_auto_block(request):
                if host:
                    return _captcha(request, source, action, host)
                return _blocked(route, max(1, (block.blocked_until - timezone.now()).total_seconds()))
        if host and _captcha_needed(request, source, host):
            return _captcha(request, source, action, host)
        return None
