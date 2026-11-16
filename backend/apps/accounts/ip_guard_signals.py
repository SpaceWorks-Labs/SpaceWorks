"""What counts as a failed sign-in for the IP guard, and the rule-cache invalidation hooks.

- Django's ``user_login_failed`` (every ``authenticate`` failure, the password door's unknown
  identifiers in ``login_context`` and the native door in ``services_device_login``);
- S-B's ``security_signals.login_refused(request, user_hint, reason)`` for MFA, code and
  social refusals, connected automatically once S-B adds it.

A receiver never raises into the sign-in that sent it.
"""

import logging

from django.contrib.auth.signals import user_login_failed

logger = logging.getLogger(__name__)


def _record(request, identifier):
    from apps.accounts import ip_guard

    try:
        ip_guard.record_failure(request, identifier)
    except Exception:
        logger.exception("ip_guard_failure_not_recorded")


def on_login_failed(sender, credentials=None, request=None, **kwargs):
    credentials = credentials if isinstance(credentials, dict) else {}
    identifier = credentials.get("username") or credentials.get("email") or ""
    _record(request, identifier if isinstance(identifier, str) else "")


def on_login_refused(sender, request=None, user_hint=None, reason=None, **kwargs):
    identifier = user_hint if isinstance(user_hint, str) else getattr(user_hint, "username", "")
    _record(request, identifier or "")


def connect_signals():
    from apps.accounts import ip_rules, security_signals

    user_login_failed.connect(on_login_failed, dispatch_uid="accounts.ip_guard.login_failed")
    refused = getattr(security_signals, "login_refused", None)
    if refused is not None:
        refused.connect(on_login_refused, dispatch_uid="accounts.ip_guard.login_refused")
    ip_rules.connect_signals()
