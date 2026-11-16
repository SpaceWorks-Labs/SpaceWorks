"""Login-security signals other lanes subscribe to, without importing their code here.

``mfa_changed(user, change)`` is sent after a change to someone's second factors has
committed. S-B connects the ``mfa_changed`` alert email to it. ``change`` is one of
``MFA_CHANGES``. Receivers must never raise into the sender: ``send_mfa_changed`` uses
``send_robust`` and logs failures.

``login_refused(request, user_hint, reason)`` (S-B) is sent at once, never on commit, for
every refused second factor, emailed code and social sign-in: a refusal is usually rolled
back with its transaction, and the counters that listen (S-C's IP guard, S-B's
unusual-login failure count) must still see it. ``user_hint`` is the person or the
identifier they typed; ``reason`` a short code, never a secret.
"""

import logging

from django.db import transaction
from django.dispatch import Signal

logger = logging.getLogger(__name__)

TOTP_ENABLED, TOTP_DISABLED = "totp_enabled", "totp_disabled"
PASSKEY_ADDED, PASSKEY_REMOVED = "passkey_added", "passkey_removed"
RECOVERY_REGENERATED, RESET = "recovery_regenerated", "reset"
MFA_CHANGES = (TOTP_ENABLED, TOTP_DISABLED, PASSKEY_ADDED, PASSKEY_REMOVED, RECOVERY_REGENERATED, RESET)

mfa_changed = Signal()  # kwargs: user, change
login_refused = Signal()  # kwargs: request, user_hint, reason (S-B)


def send_mfa_changed(user, change):
    """Send after the surrounding transaction commits (immediately outside one)."""
    if change not in MFA_CHANGES:
        raise ValueError(f"Unknown MFA change: {change}")
    user_id = user.pk

    def _send():
        from apps.accounts.models import User
        target = User.objects.filter(pk=user_id).first()
        if target is None:
            return
        for receiver, result in mfa_changed.send_robust(sender=User, user=target, change=change):
            if isinstance(result, Exception):
                logger.error("mfa_changed_receiver_failed", extra={"receiver": repr(receiver), "change": change},
                             exc_info=result)

    transaction.on_commit(_send)


def send_login_refused(request, user_hint, reason):
    """Tell the failure counters about one refused sign-in step; never raises."""
    from apps.accounts.models import User
    for receiver, result in login_refused.send_robust(sender=User, request=request, user_hint=user_hint,
                                                      reason=reason):
        if isinstance(result, Exception):
            logger.error("login_refused_receiver_failed", extra={"receiver": repr(receiver), "reason": reason},
                         exc_info=result)
