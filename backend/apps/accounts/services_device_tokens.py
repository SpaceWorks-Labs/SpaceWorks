from django.utils.translation import gettext
import hashlib
import hmac
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.settings import api_settings

from apps.accounts import audit_events
from apps.accounts.native_app_identity import registration_is_eligible
from apps.accounts.models import User
from apps.accounts.models_devices import (
    DeviceGrant,
    DeviceRefreshFamily,
    DeviceRefreshToken,
)
from apps.accounts.services_tokens import blacklist_device_family
from apps.accounts.native_app_version import assert_supported
from apps.accounts.services_staff_grants import LOST, UNSERVABLE, revoke_staff_grants, staff_role_state
from apps.accounts.tokens import SpaceWorksRefreshToken, current_auth_generation
from apps.accounts.session_issuance import lock_session_user
from apps.accounts.staff_identity import has_staff_role, is_person
from apps.accounts.restricted_admission import state_may_sign_in


def mobile_grant_creation_enabled():
    """Discovery and enforcement share the same deployment-level module gate."""
    from apps.makerspaces.deployment_modules import mobile_module_enabled

    return bool(mobile_module_enabled())


def assert_mobile_grant_creation_enabled():
    """Refuse new grants while preserving already-issued device sessions."""
    if not mobile_grant_creation_enabled():
        raise AuthenticationFailed(gettext("Mobile device sessions are not enabled."))


def token_fingerprint(raw):
    return hmac.new(settings.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()


@transaction.atomic
def issue_device_token_pair(user, grant, *, family=None):
    from apps.backup.recovery import assert_token_issuance_allowed
    from apps.accounts.surface_policy import assert_surface

    user = lock_session_user(user)
    if not is_person(user):
        raise AuthenticationFailed(gettext("Invalid device authorization."))
    assert_surface(user, "member")
    if grant is None or grant.user_id != user.pk:
        raise AuthenticationFailed(gettext("Invalid device authorization."))
    assert_token_issuance_allowed(user)
    staff = grant.authority == DeviceGrant.Authority.STAFF
    if grant.authority != DeviceGrant.Authority.MEMBER and user.access_status != user.AccessStatus.ACTIVE:
        # Decision 361: a restricted or suspended person holds member grants only.
        raise AuthenticationFailed(gettext("Invalid device authorization."))
    if staff or grant.authority == DeviceGrant.Authority.EVENT:
        from apps.accounts.mfa_policy import VERIFIED, source_for
        if source_for(user) != VERIFIED:
            raise AuthenticationFailed(gettext("Native staff and event sessions require MFA."))
    grant = DeviceGrant.objects.select_for_update().filter(pk=grant.pk, user=user).first()
    if (grant is None or grant.status != grant.Status.ACTIVE
            or grant.revoked_at is not None or not registration_is_eligible(grant.registration)
            or grant.credential_generation != user.credential_generation
            or (grant.authority == DeviceGrant.Authority.STAFF) != staff
            or staff and (grant.staff_makerspace_id is None
                          or grant.registration.makerspace_id not in (None, grant.staff_makerspace_id)
                          or not has_staff_role(user, grant.staff_makerspace_id))):
        raise AuthenticationFailed(gettext("Invalid device authorization."))
    if family is not None:
        family = DeviceRefreshFamily.objects.select_for_update().get(pk=family.pk)
        if family.revoked_at or family.user_id != user.pk or family.grant_id != grant.pk:
            raise AuthenticationFailed(gettext("Invalid device authorization."))
    family = family or DeviceRefreshFamily.objects.create(grant=grant, user=user)
    refresh = SpaceWorksRefreshToken.for_user(user, web_session=False)
    refresh["surface"] = "member"
    refresh["device_grant_id"] = str(grant.pk)
    refresh["device_family_id"] = str(family.pk)
    raw = str(refresh)
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
    OutstandingToken.objects.filter(jti=refresh["jti"], user=user).update(token=raw)
    DeviceRefreshToken.objects.create(
        family=family,
        jti=refresh["jti"],
        token_fingerprint=token_fingerprint(raw),
        expires_at=datetime.fromtimestamp(refresh["exp"], tz=timezone.get_current_timezone()),
    )
    return str(refresh.access_token), raw, family


def rotate_device_refresh(raw, *, app_version=None):
    try:
        claims = UntypedToken(raw)
    except TokenError as exc:
        raise AuthenticationFailed(gettext("Invalid device refresh token.")) from exc
    if claims.get("token_type") != "refresh":
        raise AuthenticationFailed(gettext("Invalid device refresh token."))
    jti = claims.get("jti")
    family_id = claims.get("device_family_id")
    grant_id = claims.get("device_grant_id")
    if not all((jti, family_id, grant_id)):
        raise AuthenticationFailed(gettext("Invalid device refresh token."))

    replay = revoked = False
    result = None
    # Match all issuers' User -> registration/credential order. This lookup is only discovery;
    # the joined token/family owner is checked again after obtaining the lock.
    owner_id = DeviceRefreshToken.objects.filter(jti=jti, token_fingerprint=token_fingerprint(raw)).values_list(
        "family__user_id", flat=True).first()
    if owner_id is None:
        raise AuthenticationFailed(gettext("Invalid device refresh token."))
    with transaction.atomic():
        try:
            user = User.objects.select_for_update(no_key=True).get(pk=owner_id)
        except User.DoesNotExist as exc:
            raise AuthenticationFailed(gettext("Invalid device refresh token.")) from exc
        row = (
            DeviceRefreshToken.objects.select_for_update(of=("self",))
            .select_related("family__grant__registration", "family__user")
            .filter(jti=jti, token_fingerprint=token_fingerprint(raw))
            .first()
        )
        if (row is None or str(row.family_id) != str(family_id) or row.family.user_id != user.pk
                or str(claims.get(api_settings.USER_ID_CLAIM)) != str(getattr(user, api_settings.USER_ID_FIELD))):
            raise AuthenticationFailed(gettext("Invalid device refresh token."))
        family, grant = row.family, row.family.grant
        if str(claims.get("auth_generation") or "") != current_auth_generation():
            # A cutover (A+2) or a recovery bumped the deployment generation: an old
            # refresh never rides it, whatever its own credential generation says.
            if family.revoked_at is None:
                blacklist_device_family(family, revoke_grant=True)
            revoked = True
    if revoked:
        audit_events.record_auth_event(user, "auth.refresh_rejected", target=user,
                                       meta={"reason": "auth_generation_mismatch"})
        raise AuthenticationFailed({"detail": gettext("This session was signed out. Sign in again."),
                                    "code": "session_revoked"}, code="session_revoked")
    # Refused before anything rotates, so the same refresh works after the app updates.
    assert_supported(grant.platform, app_version)
    with transaction.atomic():
        user = User.objects.select_for_update(no_key=True).get(pk=owner_id)
        row = (
            DeviceRefreshToken.objects.select_for_update(of=("self",))
            .select_related("family__grant__registration", "family__user")
            .filter(jti=jti, token_fingerprint=token_fingerprint(raw))
            .first()
        )
        if row is None or str(row.family_id) != str(family_id) or row.family.user_id != user.pk:
            raise AuthenticationFailed(gettext("Invalid device refresh token."))
        family, grant = row.family, row.family.grant
        from apps.accounts.surface_policy import validate_account_token
        validate_account_token(user, claims)
        from apps.accounts.session_issuance import validate_session_generation
        validate_session_generation(user, claims)
        if not is_person(user) or grant.user_id != user.pk:
            raise AuthenticationFailed(gettext("Invalid device refresh token."))
        staff_state = (staff_role_state(user, grant.staff_makerspace_id)
                       if grant.authority == DeviceGrant.Authority.STAFF else None)
        if grant.authority == DeviceGrant.Authority.EVENT:  # #173: the event role is the grant's life.
            from apps.accounts.services_event_grants import event_role_state
            staff_state = LOST if event_role_state(user, grant.event_id) != "active" else None
        unusable = bool(
            row.rotated_at or row.blacklisted_at or family.revoked_at
            or str(grant.pk) != str(grant_id)
        )
        if unusable:
            blacklist_device_family(family, revoke_grant=True, reuse=True)
            replay = True
        elif (
            user.is_tenant_dump_stub
            or not user.is_active
            or user.deletion_requested_at is not None
            or not state_may_sign_in(user)
            # Decision 361: a restricted or suspended person keeps refreshing a MEMBER grant only.
            or (user.access_status != user.AccessStatus.ACTIVE and grant.authority != DeviceGrant.Authority.MEMBER)
        ):
            blacklist_device_family(family, revoke_grant=True)
        elif (
            grant.status != grant.Status.ACTIVE
            or not registration_is_eligible(grant.registration)
        ):
            blacklist_device_family(family)
        elif staff_state == LOST and grant.authority == DeviceGrant.Authority.EVENT:
            from apps.accounts.services_event_grants import revoke_event_grants
            revoke_event_grants(user, grant.event_id, reason="event_role_ended")
        elif staff_state == LOST:
            revoke_staff_grants(user, grant.staff_makerspace_id, reason="staff_role_revoked")
        elif staff_state == UNSERVABLE:
            pass
        else:
            try:
                SpaceWorksRefreshToken(raw).blacklist()
            except TokenError as exc:
                blacklist_device_family(family, revoke_grant=True, reuse=True)
                replay = True
            if not replay:
                row.rotated_at = timezone.now()
                row.blacklisted_at = row.rotated_at
                row.save(update_fields=["rotated_at", "blacklisted_at"])
                from apps.accounts.mfa_policy import assert_verified, restore_proof
                assert_verified(user, claims)
                restore_proof(user, claims)
                access, refresh, _ = issue_device_token_pair(user, grant, family=family)
                result = access, refresh, grant, user
    if replay:
        audit_events.record_auth_event(
            None, "auth.device_refresh_reuse",
            meta={"family_hash": audit_events.fingerprint(family_id)},
        )
        raise AuthenticationFailed(gettext("Invalid device refresh token."))
    if result is None:
        raise AuthenticationFailed(gettext("Device authorization is no longer active."))
    return result
