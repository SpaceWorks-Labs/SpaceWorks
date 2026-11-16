"""Which ways in one person still has: the single answer every lockout guard shares.

Four places ask "would this person still be able to sign in?": the platform login-method
switches (`login_methods_validation`), unlinking a sign-in provider, unlinking a phone number
and removing a passkey. They used to answer it differently -- the switches and the unlink
guards counted only a password and linked providers, so a member who signs in by phone or
passkey could be stranded by switching phone sign-in off, or was refused an unlink that was
perfectly safe. One function now answers for all four.

A way in counts only when this deployment would accept it under the given policy:

* ``password`` -- a usable password, and either the member password switch is on or the
  person holds a staff role (the switch never closes a staff password door, #62);
* a provider key -- a linked identity whose provider is still available (built-in
  provider switched on with keys, or an enabled OIDC provider);
* ``phone`` -- a verified number, phone sign-in switched on and an SMS provider configured;
* ``passkey`` -- a registered passkey while passkeys are switched on.

Emailed password reset is deliberately not counted, matching the original guard: it is a
recovery route, not a credential, and a member without a password cannot be assumed to own
the mailbox on file.
"""

import logging

from apps.accounts.staff_identity import has_staff_role, is_person

logger = logging.getLogger(__name__)


def phone_ready(policy):
    """Phone sign-in is switched on AND an SMS provider is configured. Fails closed: a guard
    that cannot prove phone sign-in works must not count a phone as a way in."""
    if not policy.phone_enabled:
        return False
    try:
        from apps.integrations.sms import sms_configured
        return bool(sms_configured())
    except Exception:  # noqa: BLE001 - see docstring
        logger.exception("credential_inventory_sms_unreadable")
        return False


def ways_in(user, policy, providers, *, phone_ok=None, drop_identity_pk=None,
            drop_phone=False, drop_passkey_pk=None):
    """The ways ``user`` could sign in under ``policy`` with ``providers`` available, after
    optionally dropping one identity, the phone, or one passkey (the thing being removed)."""
    ways = set()
    if user.has_usable_password() and (policy.password_enabled or not is_person(user) or has_staff_role(user)):
        ways.add("password")
    for identity in user.social_identities.all():
        if identity.pk != drop_identity_pk and identity.provider in providers:
            ways.add(identity.provider)
    if phone_ok is None:
        phone_ok = phone_ready(policy)
    if phone_ok and not drop_phone and user.phone_e164 and user.phone_verified_at:
        ways.add("phone")
    if policy.passkeys_enabled:
        passkeys = user.webauthn_credentials.all()
        if drop_passkey_pk is not None:
            passkeys = passkeys.exclude(pk=drop_passkey_pk)
        if passkeys.exists():
            ways.add("passkey")
    return ways


def would_strand(user, **drop):
    """True when removing the named credential leaves ``user`` no way in today.

    Unlike the platform switches this is not "only newly stranded": a person may never remove
    their last credential, even one that is unusable right now (a provider switched off, SMS
    not configured), because switching that back on is how they get in again.
    """
    from apps.accounts.models_login_methods import PlatformLoginMethods
    from apps.accounts.social_staff_providers import surviving_identities

    policy = PlatformLoginMethods.load()
    # Available providers, narrowed to staff-capable ones for the platform account.
    providers = set(surviving_identities(user, user.social_identities.all()).values_list("provider", flat=True))
    return not ways_in(user, policy, providers, phone_ok=phone_ready(policy), **drop)
