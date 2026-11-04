from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts import audit_events, rbac
from apps.accounts.models import User
from apps.accounts.models_social import SocialDelivery, SocialSurface
from apps.accounts.services_device_tokens import (
    issue_device_token_pair,
)
from apps.accounts.services_device_grants import (
    DeviceGrantCreationRetryRequired, issue_first_device_session,
)
from apps.accounts.services_staff_authority import has_local_staff_authority
from apps.makerspaces.origin_scope import (
    AMBIGUOUS_STAFF_ORIGIN_SCOPE,
    NO_STAFF_ORIGIN_SCOPE,
    staff_origin_scope,
)
from apps.accounts.staff_identity import is_person


def assert_social_user_active(user):
    if (
        not is_person(user)
        or user.is_tenant_dump_stub
        or not user.is_active
        or user.retired_at is not None
        or user.deletion_requested_at is not None
        or user.access_status != User.AccessStatus.ACTIVE
    ):
        from apps.accounts.services_social_identity import SocialResolutionError

        raise SocialResolutionError("access_denied", 403)


def assert_staff_authority(user, request):
    from apps.accounts.services_social_identity import SocialResolutionError

    scope = getattr(request, "selected_makerspace_id", None) or (
        staff_origin_scope(request) if request is not None else NO_STAFF_ORIGIN_SCOPE
    )
    if scope is AMBIGUOUS_STAFF_ORIGIN_SCOPE:
        raise SocialResolutionError("staff_access_required", 403)
    if user.is_superuser or user.role == User.Role.SUPERADMIN:
        if scope is NO_STAFF_ORIGIN_SCOPE:
            return
    if has_local_staff_authority(
        user, makerspace_id=None if scope is NO_STAFF_ORIGIN_SCOPE else scope,
    ):
        return
    if scope is NO_STAFF_ORIGIN_SCOPE:
        if rbac.has_any_org_authority(user):
            return
        from apps.organizations.governance import has_any_governance

        if has_any_governance(user):
            return
    elif rbac.effective_actions(user, scope):
        return
    from apps.makerspaces.resource_grant_sources import has_authority
    if has_authority(user, makerspace_ids=None if scope is NO_STAFF_ORIGIN_SCOPE else [scope]):
        return
    raise SocialResolutionError("staff_access_required", 403)


class SocialDeviceGrantRetryRequired(Exception):
    """The pre-grant inputs were burned before device issuance could finish."""


@transaction.atomic
def issue_social_session(
    user, *, surface, delivery, nonce_row,
    verified_attestation=None,
):
    if surface != SocialSurface.MEMBER:
        from apps.accounts.services_social_identity import SocialResolutionError

        raise SocialResolutionError("social_invalid", 403)
    from apps.accounts.credential_locks import lock_token_issuance
    # Refuse an inactive or non-member account with its 403 before taking the
    # issuance lock; the post-lock recheck still catches a concurrent change.
    assert_social_user_active(user)
    user = lock_token_issuance(user)
    assert_social_user_active(user)
    # Provider authentication stands in for local two-step sign-in for MEMBERS only (#62):
    # a person MFA is mandatory for never gets provider proof (their door challenged them).
    from apps.accounts.mfa_policy import required
    if not required(user):
        user._mfa_provider_verified = True
    from apps.backup.recovery import assert_token_issuance_allowed

    try:
        assert_token_issuance_allowed(user)
    except AuthenticationFailed as exc:
        if delivery == SocialDelivery.DEVICE and nonce_row.device_grant_id is None:
            raise SocialDeviceGrantRetryRequired from exc
        raise
    if delivery == SocialDelivery.DEVICE:
        grant = nonce_row.device_grant
        if grant is None:
            access, refresh, grant = _issue_first_social_session(
                user, nonce_row.attestation_challenge, verified_attestation
            )
        else:
            with transaction.atomic():
                access, refresh, _family = issue_device_token_pair(user, grant)
        return {"access": access, "refresh": refresh, "device_grant": grant}
    from apps.accounts.tokens import SpaceWorksRefreshToken

    refresh = SpaceWorksRefreshToken.for_user(user)
    refresh["surface"] = surface
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _issue_first_social_session(user, challenge, verified_attestation):
    try:
        return issue_first_device_session(
            user, challenge, verified_attestation, login_method="social",
        )
    except DeviceGrantCreationRetryRequired as exc:
        raise SocialDeviceGrantRetryRequired from exc


def social_audit_meta(provider, outcome, subject):
    return {
        "provider": provider,
        "outcome": outcome,
        "subject_hash": audit_events.fingerprint(subject),
    }


def staff_challenge(request, user, *, delivery, nonce_row=None, verified_attestation=None):
    """#62: a person MFA is mandatory for (staff and other elevated authority) still enters
    their factor after Google, Apple, GitHub or an OIDC provider. Returns the challenge
    response, or None when the sign-in may complete (members: unchanged)."""
    from apps.accounts.mfa_challenges import start
    from apps.accounts.mfa_policy import needs_challenge, required
    from apps.accounts.mfa_sessions import context, device_context
    if not (required(user) and needs_challenge(user)):
        return None
    assert_social_user_active(user)
    from apps.backup.recovery import assert_token_issuance_allowed
    assert_token_issuance_allowed(user)
    device = None
    if delivery == SocialDelivery.DEVICE:
        device = device_context(nonce_row.attestation_challenge, verified_attestation,
                                grant=nonce_row.device_grant, login_method="social")
    return start(user, context=context(request, surface=SocialSurface.MEMBER, device=device, login_method="social"))
