"""Redeem a staff-role invitation while signed in (one account per person, #63/#65).

Two calls to ``POST auth/staff-invitations/accept``:

1. ``{token, makerspace_slug}``: the signed-in person's email must equal the invitation
   address (``invite_email_mismatch`` otherwise). A fresh 6-digit code is emailed to that
   address and the answer is ``{"challenge_required": true}``. Nothing changes yet.
2. ``{token, makerspace_slug, code}``: the code proves the address now; the person gets a
   staff-track row with the invitation's role and machine-scope snapshot, granted under
   the inviter's authority (re-checked at acceptance), and their 3-day staff MFA grace
   opens (``mfa_grace.open_grace(user, "invite")``).

The invitation never creates an account and never stamps ``email_verified_at``: the code
proves the address for THIS acceptance only. Codes are stored as HMAC digests bound to
the invitation and the person, live 10 minutes and allow 5 failures per invitation.
"""

from django.utils.translation import gettext
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import login_codes
from apps.accounts.mfa_challenges import digest
from apps.accounts.models import EmailVerificationChallenge, StaffInvitation, User
from apps.accounts.staff_account_policy import (
    ALREADY_STAFF, INVITE_EMAIL_MISMATCH, StaffRoleRefused, check_staff_quota, require_authority, staff_write,
)
from apps.accounts.staff_identity import is_person
from apps.audit.services import record
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.models import Makerspace

logger = logging.getLogger(__name__)
GENERIC_ERROR = "Unable to accept this invitation. Check the link or ask for a new one."
PURPOSE = "staff_invitation"
TTL, COOLDOWN, MAX_FAILURES = timedelta(minutes=10), timedelta(seconds=60), 5


def _key(row):
    # Keeps these proofs apart from the account's own email-verification challenges.
    return f"staff-invite:{row.pk}"


def _open(token, makerspace_slug, *, lock=False):
    rows = StaffInvitation.objects.select_related("makerspace")
    if lock:
        rows = rows.select_for_update(of=("self",))
    row = rows.filter(token_digest=digest(token), makerspace__slug=makerspace_slug).first()
    if (row is None or row.accepted_at or row.revoked_at or row.expires_at <= timezone.now()
            or row.failed_attempts >= MAX_FAILURES):
        raise ValidationError({"detail": GENERIC_ERROR})
    return row


def _require_redeemer(user, row):
    if not (is_person(user) and user.is_active and user.access_status == User.AccessStatus.ACTIVE
            and not user.is_walk_in and not user.is_tenant_dump_stub):
        raise PermissionDenied(gettext("Sign in to your own account to accept a staff invitation."))
    if not user.email or user.email.strip().lower() != row.email.strip().lower():
        raise StaffRoleRefused(INVITE_EMAIL_MISMATCH,
                               "This invitation was sent to a different email address. Sign in to that account.")


def _lock_redeemable(user, token, makerspace_slug, space_id):
    # Match the lock order used by resend/revoke and serialize against switch changes.
    space = Makerspace.objects.select_for_update(no_key=True).filter(pk=space_id).first()
    if space is None:
        raise ValidationError({"detail": GENERIC_ERROR})
    row = _open(token, makerspace_slug, lock=True)
    _require_redeemer(user, row)
    require_feature(space, "staff.invitations")
    require_module(space, "email")
    return row


def accept(request, *, token, makerspace_slug, code=""):
    user = User.objects.get(pk=request.user.pk)
    if not code:
        return _challenge(user, token, makerspace_slug)
    return _complete(user, token, makerspace_slug, code)


def _challenge(user, token, makerspace_slug):
    now = timezone.now()
    original = _open(token, makerspace_slug)
    with staff_write(original.makerspace_id):
        row = _lock_redeemable(user, token, makerspace_slug, original.makerspace_id)
        challenges = EmailVerificationChallenge.objects.filter(user=user, email=_key(row))
        if challenges.filter(last_sent_at__gte=now - COOLDOWN).exists():
            raise ValidationError({"detail": gettext("A code was sent a moment ago. Wait a minute before asking again.")})
        challenges.filter(consumed_at__isnull=True).update(consumed_at=now)
        code = login_codes.new_code()
        EmailVerificationChallenge.objects.create(
            user=user, email=_key(row), code_digest=login_codes.digest(code, PURPOSE, f"{row.pk}:{user.pk}"),
            expires_at=now + TTL, last_sent_at=now)
        address, space = row.email, row.makerspace.name
    transaction.on_commit(lambda: _send_code(address, code, space))
    return {"challenge_required": True, "detail": "We emailed a 6-digit code to the invitation address."}


def _send_code(address, code, space_name):
    from apps.integrations.dispatch import dispatch_email
    try:
        dispatch_email(to_email=address, subject=gettext('Your code to accept a staff role at {space_name}').format(space_name=space_name),
                       text_body=gettext('Your code is {code}. It expires in 10 minutes and works once.\n\nIf you did not try to accept a staff invitation, ignore this email.').format(code=code),
                       stream="account", event="staff_invitation_code", audience="user",
                       connection="platform", persist_body=False, sync=True)
    except Exception as exc:
        logger.warning("staff_invitation_code_failed", extra={"error_type": type(exc).__name__})


def _complete(user, token, makerspace_slug, code):
    row, failed = _open(token, makerspace_slug), False
    with staff_write(row.makerspace_id):
        row = _lock_redeemable(user, token, makerspace_slug, row.makerspace_id)
        challenge = (EmailVerificationChallenge.objects.select_for_update()
                     .filter(user=user, email=_key(row), consumed_at__isnull=True,
                             failed_attempts__lt=MAX_FAILURES, expires_at__gt=timezone.now())
                     .order_by("-created_at").first())
        if challenge is None or not login_codes.verify(challenge.code_digest, code, PURPOSE, f"{row.pk}:{user.pk}"):
            # Counted and audited in this committed transaction; refused after it.
            if challenge is not None:
                EmailVerificationChallenge.objects.filter(pk=challenge.pk).update(failed_attempts=F("failed_attempts") + 1)
            StaffInvitation.objects.filter(pk=row.pk).update(failed_attempts=F("failed_attempts") + 1)
            record(user, "staff_invitation.accept_failed", makerspace=row.makerspace, target=row)
            failed = True
        else:
            challenge.consumed_at = timezone.now()
            challenge.save(update_fields=["consumed_at"])
            membership = _grant(user, row)
    if failed:
        raise ValidationError({"detail": gettext("That code is not right or has expired."), "code": "proof_failed"})
    from apps.accounts.staff_role_notices import notify_granted
    notify_granted(membership)
    space = row.makerspace
    return {"challenge_required": False, "detail": f"You now have a staff role at {space.name}.",
            "makerspace": {"id": space.pk, "slug": space.slug, "name": space.name}}


def _grant(user, row):
    """Inside the locked boundary: create the staff row under the inviter's authority."""
    from apps.accounts.mfa_grace import open_grace
    from apps.makerspaces.models import MakerspaceMembership
    from apps.makerspaces.staff_role_grants import grant_staff_role

    space, creator = row.makerspace, User.objects.get(pk=row.created_by_id)
    roles = list(space.roles.filter(slug__in=row.role_snapshot))
    if len(roles) != len(row.role_snapshot):
        raise ValidationError({"detail": GENERIC_ERROR})
    # The inviter's authority is re-checked now: a demoted inviter's link stops working.
    require_authority(creator, space, target=user, roles=roles)
    if MakerspaceMembership.staff_tracks.filter(makerspace=space, user=user).exists():
        raise StaffRoleRefused(ALREADY_STAFF, "You already have a staff role here.")
    check_staff_quota(space)
    membership = grant_staff_role(makerspace=space, user=user, roles=roles, actor=creator,
                                  machine_type_ids=list(row.machine_scope_snapshot),
                                  machine_ids=list(row.machine_ids_snapshot))
    row.accepted_at, row.accepted_by = timezone.now(), user
    row.save(update_fields=["accepted_at", "accepted_by"])
    record(user, "staff_invitation.accepted", makerspace=space, target=row,
           meta={"membership_id": membership.pk, "roles": row.role_snapshot})
    open_grace(user, "invite")
    return membership
