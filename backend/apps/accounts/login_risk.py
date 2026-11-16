"""The unusual-login check (#62; #66: the superadmin gets alerts only; Q4; lane S-B).

``evaluate(request, user, method)`` runs at every sign-in door before tokens are minted.
A sign-in is unusual when ANY of these holds:

- the request carries no valid remembered device (``KnownDevice``) for this person;
- the client's network (IPv4 /24, IPv6 /64) was not seen for them in 90 days;
- ``LOGIN_RISK_FAILURE_THRESHOLD`` failed sign-ins named the account in the last hour.

Only a PASSWORD sign-in (web or native) is stepped up; social, phone-code and passkey
sign-ins already proved something beyond a password, so they only record the device
(Q4). The step-up is the person's own factor when they have one (the ordinary MFA
challenge every enrolled account gets anyway); otherwise an emailed 6-digit code
(``mfa_source=email_code``: never VERIFIED, never staff proof). With no way to deliver a
code the sign-in fails OPEN with ``auth.risk_unverifiable``, and the new-device alert is
still sent. The superadmin is never stepped up, only alerted. ``security.login_risk_check``
(the strictest across the person's staff spaces; members: on) can turn the step-up off.

``record_success`` runs once a sign-in completes: it remembers the device and network and
sends the ``login_new_device`` alert for a device the person had not used before.
"""

import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from apps.accounts import audit_events, device_memory, login_risk_networks
from apps.accounts.login_security_contract import LOGIN_RISK_CHECK, PURPOSE_RISK

logger = logging.getLogger(__name__)
STEP_UP_METHODS = frozenset({"password"})
NEW_DEVICE, NEW_NETWORK, RECENT_FAILURES = "new_device", "new_network", "recent_failures"


@dataclass(frozen=True)
class Decision:
    reasons: tuple
    step_up: bool

    @property
    def unusual(self):
        return bool(self.reasons)


def is_superadmin(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "role", None) == "superadmin")


def check_enabled(user):
    from apps.makerspaces.security_settings_person import strictest_for_staff
    try:
        return bool(strictest_for_staff(user, LOGIN_RISK_CHECK))
    except Exception:  # an unreadable policy keeps the check on
        logger.warning("login_risk_check_unreadable", exc_info=True)
        return True


def evaluate(request, user, method):
    from apps.accounts.login_risk_signals import recent_failures
    reasons = []
    if device_memory.lookup(request, user) is None:
        reasons.append(NEW_DEVICE)
    if not login_risk_networks.is_familiar(user, request):
        reasons.append(NEW_NETWORK)
    if recent_failures(user) >= settings.LOGIN_RISK_FAILURE_THRESHOLD:
        reasons.append(RECENT_FAILURES)
    step_up = bool(reasons) and method in STEP_UP_METHODS and not is_superadmin(user) and check_enabled(user)
    return Decision(tuple(reasons), step_up)


def code_deliverable(user):
    from apps.integrations.email import email_enabled
    try:
        return bool((user.email or "").strip()) and email_enabled()
    except Exception:
        logger.warning("login_code_channel_unreadable", exc_info=True)
        return False


def step_up(request, user, *, method, context):
    """For a door that would otherwise mint tokens now: the risk challenge response, or
    None to proceed (usual sign-in, check off, or no channel: fail open)."""
    decision = evaluate(request, user, method)
    if not decision.step_up:
        return None
    if not code_deliverable(user):
        audit_events.record_auth_event(user, "auth.risk_unverifiable", target=user,
                                       meta={"reasons": list(decision.reasons)})
        return None
    from apps.accounts.mfa_challenges import start
    result = start(user, context=context, purpose=PURPOSE_RISK)
    audit_events.record_auth_event(user, "auth.login_risk_challenged", target=user,
                                   meta={"reasons": list(decision.reasons)})
    return result


def record_success(request, user, *, method, web):
    """Remember the device and network of a completed sign-in; returns the device token
    (a web view sets it with ``device_memory.attach``; native returns it as
    ``device_trust``). Never fails the sign-in."""
    try:
        with transaction.atomic():  # a savepoint: a failure here never breaks the sign-in
            had_devices = user.known_devices.exists()
            row, token, created = device_memory.remember(request, user)
            network = login_risk_networks.remember(user, request)
    except Exception:
        logger.exception("login_risk_record_failed", extra={"method": method})
        return None
    if created:
        audit_events.record_auth_event(user, "auth.device_remembered", target=user, meta={"method": method})
        if had_devices:
            from apps.accounts import security_alerts
            security_alerts.new_device(user, network_label=network, ua_label=row.ua_label)
    if web:
        device_memory.stash(request, token)
    return token
