"""The MFA-reset rule (#66, consistent with #110): who may clear someone's second factors.

``reset(actor, person, reason, makerspace=None)`` clears the authenticator, every passkey
and the recovery codes, bumps ``UserMFA.version`` and revokes every session and device
grant. It is allowed for:

- the platform superadmin, always: the ``/control/`` user action (control step-up), the
  host command ``manage.py reset_mfa`` and Lane D's console surface for a space;
- a Space Manager of ``makerspace`` ONLY when every elevated authority the person holds
  is inside that space (staff roles there and nowhere else, no organization authority,
  no resource grant elsewhere) and the person is not a Space Manager themselves.

Everyone else is refused with ``mfa_reset_not_allowed``. The person's staff grace is
closed: they enrol again before using staff screens (member features keep working).
Audited as ``auth.mfa_reset`` with the rule used; ``mfa_changed`` is signalled.
"""

import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.login_security_contract import MFA_RESET_NOT_ALLOWED

RULE_SUPERADMIN, RULE_SPACE_MANAGER, RULE_HOST = "superadmin", "space_manager", "host"


class MfaResetNotAllowed(PermissionDenied):
    def __init__(self, detail="Only a platform superadmin can reset this person's two-step sign-in."):
        super().__init__({"detail": detail, "code": MFA_RESET_NOT_ALLOWED})


def _authority_only_in(person, makerspace_id):
    from apps.accounts.rbac import has_any_org_authority
    from apps.makerspaces.models import Makerspace, MakerspaceMembership
    from apps.makerspaces.resource_grant_sources import has_authority
    staff_spaces = set(MakerspaceMembership.staff_tracks.filter(user=person, status="active")
                       .values_list("makerspace_id", flat=True))
    if staff_spaces - {makerspace_id} or has_any_org_authority(person):
        return False
    elsewhere = Makerspace.objects.exclude(pk=makerspace_id).values_list("pk", flat=True)
    return not has_authority(person, makerspace_ids=elsewhere)


def rule_for(actor, person, makerspace=None):
    """The rule that lets ``actor`` reset ``person`` (in ``makerspace``), else None."""
    from apps.accounts import rbac
    from apps.accounts.platform_authority import is_platform_superadmin
    from apps.accounts.staff_identity import is_person
    if actor is None or person is None or not is_person(person) or actor.pk == person.pk:
        return None
    if is_platform_superadmin(actor):
        return RULE_SUPERADMIN
    if makerspace is None:
        return None
    from apps.makerspaces.security_settings import SPACE, editor_via
    if editor_via(actor, makerspace) != SPACE:
        return None
    if rbac.is_space_manager_identity(person, makerspace.pk) or not _authority_only_in(person, makerspace.pk):
        return None
    return RULE_SPACE_MANAGER


def can_reset(actor, person, makerspace=None):
    return rule_for(actor, person, makerspace) is not None


def _clear(person, actor):
    from apps.accounts.credential_revocation import revoke_all_credentials
    from apps.accounts.models import User
    from apps.accounts.models_mfa import MFAChallenge, UserMFA
    from apps.accounts.models_webauthn import WebAuthnCeremony, WebAuthnCredential
    revoke_all_credentials(person, reason="auth.mfa_reset", actor=actor)
    with transaction.atomic():
        person = User.objects.select_for_update().get(pk=person.pk)
        mfa, _ = UserMFA.objects.select_for_update().get_or_create(user=person)
        mfa.secret, mfa.enabled_at, mfa.last_step = "", None, -1
        mfa.recovery_digests, mfa.version = [], uuid.uuid4()
        mfa.save()
        passkeys = WebAuthnCredential.objects.filter(user=person).delete()[0]
        WebAuthnCeremony.objects.filter(user=person, consumed_at__isnull=True).update(consumed_at=timezone.now())
        MFAChallenge.objects.filter(user=person, consumed_at__isnull=True).update(consumed_at=timezone.now())
    return person, passkeys


def reset(actor, person, reason, makerspace=None, *, rule=None):
    """Apply the rule, clear every factor, revoke sessions; return the rule used."""
    from apps.accounts import security_signals
    from apps.accounts.mfa_grace import close_grace
    from apps.audit import services as audit
    reason = str(reason or "").strip()
    if not 3 <= len(reason) <= 300:
        raise PermissionDenied({"detail": "Give a reason (3 to 300 characters).", "code": "invalid_reason"})
    rule = rule or rule_for(actor, person, makerspace)
    if rule is None:
        raise MfaResetNotAllowed()
    if makerspace is not None:
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(makerspace.pk)
    person, passkeys = _clear(person, actor)
    close_grace(person, after_reset=True)
    audit.record(actor, "auth.mfa_reset", target=person, makerspace=makerspace,
                 meta={"rule": rule, "reason": reason, "passkeys_removed": passkeys})
    security_signals.send_mfa_changed(person, security_signals.RESET)
    return rule
