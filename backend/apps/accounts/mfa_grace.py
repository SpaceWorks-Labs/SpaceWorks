"""The 3-day staff two-step grace (#128 C-1; #135 Q-A1-Q-A3).

A person who gains elevated authority without a second factor may use staff routes for
three days; afterwards staff routes refuse with ``mfa_enrollment_required`` until they
enrol. Member features are never blocked. One grace per person, ever (Q-A2): the
``StaffMfaGrace`` row is one-to-one, so a re-grant after it ended is blocked at once.

When the clock starts:
- ``grant``: a staff-track row became active for an unenrolled person (membership signal);
- ``invite`` / ``merge``: the invitation and account-merge flows call ``open_grace``;
- ``upgrade``: anyone else who is elevated and unenrolled gets theirs the first time the
  system looks (sign-in payload or a staff route) -- this is how staff who existed before
  release 2 get three days from their first sign-in (Q-A1).

During the grace, the routes in ``STRICT_ROUTES`` still need real two-step proof
(Q-A3: security settings, PII windows, exports, credential resets and role changes).
Enrolling closes the grace; an MFA reset closes it too (the person enrols again before
using staff screens).
"""

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.login_security_contract import (
    GRACE_GRANT, GRACE_SOURCES, GRACE_UPGRADE, STAFF_MFA_GRACE,
)

logger = logging.getLogger(__name__)

# #135 Q-A3: staff routes the grace never opens. Route names, matched in surface_policy.
STRICT_ROUTES = frozenset({
    # Security settings and superadmin PII windows.
    "admin-makerspace-security-settings", "admin-makerspace-security-lock", "admin-makerspace-pii-access",
    # Exports.
    "data-export-list-create", "data-export-detail", "data-export-download-url",
    # Credential resets and role changes.
    "admin-staff-roles", "admin-staff-roles-detail", "admin-staff-roles-revoke", "admin-staff-roles-restore",
    "admin-staff-roles-mfa-reset", "admin-staff-invitations", "admin-staff-invitation-revoke",
    "admin-staff-invitation-resend",
})


def _row(user):
    from apps.accounts.models_mfa_grace import StaffMfaGrace
    return StaffMfaGrace.objects.filter(user_id=user.pk).first()


def _due(user):
    from apps.accounts import mfa_policy
    return mfa_policy.required(user) and not mfa_policy.is_enrolled(user)


def open_grace(user, source=GRACE_GRANT, *, now=None):
    """Start this person's grace if they are elevated, unenrolled and never had one.

    Returns the row (new or existing) or None when no grace applies. Idempotent and
    safe under races: the one-to-one key decides who wins.
    """
    from apps.accounts.models_mfa_grace import StaffMfaGrace

    if source not in GRACE_SOURCES:
        raise ValueError(f"Unknown grace source: {source}")
    if getattr(user, "pk", None) is None:
        return None
    existing = _row(user)
    if existing is not None or not _due(user):
        return existing
    started = now or timezone.now()
    try:
        with transaction.atomic():
            row = StaffMfaGrace.objects.create(user_id=user.pk, started_at=started, source=source,
                                               ends_at=started + STAFF_MFA_GRACE)
    except IntegrityError:
        return _row(user)
    from apps.audit import services as audit
    audit.record(user, "auth.staff_mfa_grace_started", target=user, meta={"source": source})
    return row


def close_grace(user, *, now=None, after_reset=False):
    """End an open grace now: the person enrolled, or (``after_reset``) an MFA reset
    cleared their factors and they must enrol again before using staff screens."""
    from apps.accounts.models_mfa_grace import StaffMfaGrace

    now = now or timezone.now()
    row = _row(user)
    if row is None:
        if not (after_reset and _due(user)):
            return
        # Never had one: record it as used, so the reset cannot open a fresh grace.
        try:
            with transaction.atomic():
                StaffMfaGrace.objects.create(user_id=user.pk, started_at=now, source=GRACE_UPGRADE,
                                             ends_at=now + timedelta(microseconds=1))
        except IntegrityError:
            pass
        return
    if row.ends_at > now:
        row.ends_at = max(now, row.started_at + timedelta(microseconds=1))
        row.save(update_fields=["ends_at"])


def grace_ends_at(user, *, open_if_due=True):
    """When an unenrolled elevated person's grace ends (past or future), else None."""
    if getattr(user, "pk", None) is None or not _due(user):
        return None
    row = open_grace(user, GRACE_UPGRADE) if open_if_due else _row(user)
    return row.ends_at if row is not None else None


def is_open(user, *, now=None):
    ends_at = grace_ends_at(user)
    return ends_at is not None and ends_at > (now or timezone.now())


def _membership_saved(sender, instance, **kwargs):
    if kwargs.get("raw") or getattr(instance, "track", None) != "staff" or instance.status != "active":
        return
    user_id = instance.user_id

    def _after_commit():
        from apps.accounts.models import User
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return
        try:
            open_grace(user, GRACE_GRANT)
        except Exception:  # never fail the role grant itself; the lazy path still opens one
            logger.exception("staff_mfa_grace_open_failed", extra={"user_id": user_id})

    transaction.on_commit(_after_commit)


def connect_signals():
    from django.db.models.signals import post_save
    from apps.makerspaces.models import MakerspaceMembership

    post_save.connect(_membership_saved, sender=MakerspaceMembership,
                      dispatch_uid="accounts.mfa_grace.membership_saved")
