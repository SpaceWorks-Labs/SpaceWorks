"""'This wasn't me': what one alert link does (#62; lane S-B).

The link is ``/security/not-me#token=<signing.dumps({"a": alert id, "n": nonce})>``: the
token sits in the URL FRAGMENT, so it never reaches a server log, a proxy or a Referer;
the page POSTs it to ``auth/security-alerts/not-me`` explicitly, cookie-less. Using it, in
one transaction:

- signs the account out everywhere (``revoke_all_credentials``: sessions, refresh tokens,
  device grants, pending proofs) and forgets every remembered device;
- turns the password off (``set_unusable_password``) and requests a reset code to the
  account email through the ordinary recovery queue;
- marks this alert used and expires every other outstanding alert of the person.

No second factor is removed: if the person also lost their authenticator, the answer
names who the MFA-reset rule lets reset it. Any refusal is one generic
``security_alert_used`` (unknown, forged, expired or already used).
"""

import hmac
import logging
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.login_security_contract import SECURITY_ALERT_USED

logger = logging.getLogger(__name__)


class SecurityAlertUsed(ValidationError):
    def __init__(self):
        super().__init__({"detail": "This link has already been used or has expired.", "code": SECURITY_ALERT_USED})


def _payload(token):
    from apps.accounts.security_alerts import TOKEN_SALT
    try:
        data = signing.loads(token, salt=TOKEN_SALT,
                             max_age=timedelta(days=settings.SECURITY_ALERT_LINK_TTL_DAYS))
    except (signing.BadSignature, TypeError, ValueError):
        raise SecurityAlertUsed() from None
    if not isinstance(data, dict) or not isinstance(data.get("a"), int) or not isinstance(data.get("n"), str):
        raise SecurityAlertUsed()
    return data["a"], data["n"]


def _live(alert_id, nonce, *, lock=False):
    from apps.accounts.models import SecurityAlert
    from apps.accounts.security_alerts import nonce_digest
    rows = SecurityAlert.objects.select_for_update() if lock else SecurityAlert.objects
    row = rows.filter(pk=alert_id).first()
    if (row is None or row.used_at is not None or row.expires_at <= timezone.now()
            or not hmac.compare_digest(row.nonce_digest, nonce_digest(nonce))):
        raise SecurityAlertUsed()
    return row


def expire_outstanding(user, *, now=None):
    """Every unused alert of ``user`` stops working (an alert used, a reset completed)."""
    from apps.accounts.models import SecurityAlert
    return SecurityAlert.objects.filter(user_id=user.pk, used_at__isnull=True).update(used_at=now or timezone.now())


def mfa_reset_contacts(user):
    """Who may reset this person's second factors under the MFA-reset rule."""
    from apps.accounts.mfa_reset import _authority_only_in
    from apps.accounts.rbac import is_space_manager_identity
    from apps.makerspaces.models import MakerspaceMembership
    spaces = []
    memberships = (MakerspaceMembership.all_tracks.filter(user=user, status="active")
                   .select_related("makerspace").order_by("makerspace__name"))
    for membership in memberships[:20]:
        space = membership.makerspace
        if any(item["slug"] == space.slug for item in spaces):
            continue
        if not is_space_manager_identity(user, space.pk) and _authority_only_in(user, space.pk):
            spaces.append({"name": space.name, "slug": space.slug})
    return {"superadmin": True, "space_managers_of": spaces}


def use(token, request):
    alert_id, nonce = _payload(token)
    row = _live(alert_id, nonce)  # cheap refusal before any lock
    from apps.accounts import audit_events, device_memory
    from apps.accounts.credential_revocation import revoke_all_credentials
    from apps.accounts.models import User
    user = User.objects.get(pk=row.user_id)
    with transaction.atomic():
        # The shared credential lock order first (Tenant -> Invitations -> User -> ...).
        revoke_all_credentials(user, reason="account.not_me", actor=user)
        row = _live(alert_id, nonce, lock=True)
        now = timezone.now()
        locked = User.objects.select_for_update().get(pk=row.user_id)
        device_memory.revoke_all(locked, now=now)
        locked.set_unusable_password()
        locked.save(update_fields=["password"])
        expire_outstanding(locked, now=now)
        audit_events.record_auth_event(locked, "auth.not_me_used", target=locked, meta={"kind": row.kind})
        email = (locked.email or "").strip()
        platform = bool(locked.is_superuser or locked.role == User.Role.SUPERADMIN)
        transaction.on_commit(lambda: _request_reset(email, platform, request))
    return {"signed_out": True, "password_reset_requested": bool(email),
            "mfa_reset": mfa_reset_contacts(locked) if not platform else {"superadmin": True, "space_managers_of": []}}


def _request_reset(email, platform, request):
    if not email:
        return
    from apps.accounts.password_reset_context import recovery_origin
    from apps.accounts.services_password_reset import PasswordResetCooldown, request_password_reset
    try:
        request_password_reset(email, context="platform" if platform else "member", origin=recovery_origin(request))
    except PasswordResetCooldown:
        pass
    except Exception:
        logger.exception("not_me_reset_request_failed")
