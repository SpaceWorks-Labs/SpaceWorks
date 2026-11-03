"""Inputs of the unusual-login check that arrive as signals (lane S-B).

- Every failed sign-in step (Django's ``user_login_failed`` and S-B's ``login_refused``)
  bumps a one-hour counter for the account it named, from any address: the check's third
  trigger is ``LOGIN_RISK_FAILURE_THRESHOLD`` failures in that hour.
- django-axes ``user_locked_out`` sends the ``account_locked`` alert, at most once an hour
  per account.

Counters are cache-only and fail open (an outage counts nothing). Receivers never raise.
"""

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)
FAILURE_WINDOW_SECONDS = 3600


def _key(identifier):
    from apps.accounts.ip_guard import account_key
    value = account_key(identifier)
    return f"sec:riskf:{value}" if value else ""


def _bump(identifier):
    key = _key(identifier)
    if not key:
        return
    try:
        if not cache.add(key, 1, FAILURE_WINDOW_SECONDS):
            cache.incr(key)
    except Exception:
        logger.warning("login_risk_cache_unavailable", exc_info=True)


def recent_failures(user):
    """Failures in the last hour that named this person (username or email)."""
    counts = [0]
    for identifier in {user.username, (user.email or "").strip().lower()} - {""}:
        try:
            counts.append(int(cache.get(_key(identifier)) or 0))
        except Exception:
            logger.warning("login_risk_cache_unavailable", exc_info=True)
    return max(counts)


def on_login_failed(sender, credentials=None, request=None, **kwargs):
    credentials = credentials if isinstance(credentials, dict) else {}
    identifier = credentials.get("username") or credentials.get("email") or ""
    if isinstance(identifier, str):
        _bump(identifier)


def on_login_refused(sender, request=None, user_hint=None, reason=None, **kwargs):
    if isinstance(user_hint, str):
        _bump(user_hint)
    elif getattr(user_hint, "username", ""):
        _bump(user_hint.username)


def on_user_locked_out(sender, request=None, username=None, **kwargs):
    try:
        from apps.accounts import security_alerts
        from apps.accounts.models import User
        from django.db.models import Q
        identifier = str(username or "").strip()
        if not identifier:
            return
        user = User.objects.filter(Q(username=identifier) | Q(email__iexact=identifier) & ~Q(email="")).first()
        if user is not None:
            security_alerts.account_locked(user)
    except Exception:
        logger.exception("account_locked_alert_failed")


def connect_signals():
    from django.contrib.auth.signals import user_login_failed

    from apps.accounts import security_signals
    from apps.accounts.security_alerts import on_mfa_changed
    user_login_failed.connect(on_login_failed, dispatch_uid="accounts.login_risk.login_failed")
    security_signals.login_refused.connect(on_login_refused, dispatch_uid="accounts.login_risk.login_refused")
    security_signals.mfa_changed.connect(on_mfa_changed, dispatch_uid="accounts.security_alerts.mfa_changed")
    try:
        from axes.signals import user_locked_out
    except ImportError:  # axes is a hard dependency; stay importable without it
        return
    user_locked_out.connect(on_user_locked_out, dispatch_uid="accounts.security_alerts.locked_out")
