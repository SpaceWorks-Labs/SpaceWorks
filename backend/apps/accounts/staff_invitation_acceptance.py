"""Single-use initial setup; an invitation never links or resets accounts."""
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.accounts import audit_events
from apps.accounts.mfa_challenges import digest
from apps.accounts.models import StaffInvitation, User
from apps.accounts.services_staff_invitations import authority, snapshot
from apps.accounts.staff_account_policy import require_authority
from apps.audit.services import record
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.tenant_migration.gate_runtime import tenant_write

GENERIC_ERROR = "Unable to accept this invitation. Check the link and credentials or contact the inviter."


def accept(request, *, token, makerspace_slug, password, code=""):
    candidate = StaffInvitation.objects.filter(token_digest=digest(token), makerspace__slug=makerspace_slug).first()
    if candidate is None:
        make_password(password)
        raise ValidationError({"detail": GENERIC_ERROR})
    ok = password_checked = False
    with tenant_write(candidate.makerspace_id):
        try:
            with transaction.atomic():
                space = Makerspace.objects.select_for_update(no_key=True).get(pk=candidate.makerspace_id)
                row = StaffInvitation.objects.select_for_update().get(pk=candidate.pk)
                if (row.token_digest != digest(token) or row.account_id is None
                        or row.accepted_at or row.revoked_at or row.expires_at <= timezone.now()
                        or row.failed_attempts >= 5):
                    raise ValidationError(GENERIC_ERROR)
                # Preserve Invitation -> ordered Users -> Membership lock order.
                # Nullable account/role FKs never participate in the locking query.
                users = {user.pk: user for user in User.objects.select_for_update().filter(
                    pk__in=[row.created_by_id, row.account_id],
                ).order_by("pk")}
                creator, user = users[row.created_by_id], users[row.account_id]
                authority(creator, space)
                require_authority(creator, space, target=user)
                if (not user.is_active or user.has_usable_password() or user.is_tenant_dump_stub
                        or user.access_status != User.AccessStatus.ACTIVE
                        or user.email.lower() != row.email.lower()):
                    raise ValidationError(GENERIC_ERROR)
                membership = MakerspaceMembership.objects.select_for_update().get(
                    user=user, makerspace=space, status="active")
                expected = snapshot(user, membership)
                if any(getattr(row, key) != value for key, value in expected.items()):
                    raise ValidationError(GENERIC_ERROR)
                roles = list(MakerspaceRole.objects.filter(makerspace=space, slug__in=row.role_snapshot))
                require_authority(creator, space, target=user, roles=roles)
                # Only full Space Managers/platform admins can invite: both have
                # full machine authority. Scoped helpers cannot pass this policy.
                user.set_password(password)
                password_checked = True
                validate_password(password, user)
                user.must_change_password = False
                user.email_verified_at = timezone.now()
                user.save(update_fields=["password", "must_change_password", "email_verified_at"])
                row.accepted_at, row.accepted_by = timezone.now(), user
                row.save(update_fields=["accepted_at", "accepted_by"])
                record(user, "staff.invitation_accepted", makerspace=space, target=row,
                       meta={"membership_id": membership.pk, "role_id": row.role_id})
                ok = True
        except (APIException, DjangoValidationError, IntegrityError, ObjectDoesNotExist, KeyError):
            if not password_checked:
                make_password(password)
            StaffInvitation.objects.filter(pk=candidate.pk, accepted_at__isnull=True,
                                           failed_attempts__lt=5).update(failed_attempts=F("failed_attempts") + 1)
            audit_events.record_auth_event(None, "staff.invitation_accept_failed",
                                           meta={"invitation_hash": audit_events.fingerprint(candidate.pk)})
    if not ok:
        raise ValidationError({"detail": GENERIC_ERROR})
    return {"detail": "Invitation accepted. Sign in with your staff username or email and password."}
