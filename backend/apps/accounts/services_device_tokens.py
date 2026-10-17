import hashlib
import hmac
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from apps.accounts import audit_events
from apps.accounts.credential_locks import lock_token_issuance
from apps.accounts.models import User
from apps.accounts.models_devices import (
    DeviceGrant,
    DeviceRefreshFamily,
    DeviceRefreshToken,
    NativeAppRegistration,
)
from apps.accounts.services_tokens import blacklist_device_family
from apps.accounts.tokens import SpaceWorksRefreshToken


def assert_mobile_grant_creation_enabled():
    """Refuse new grants while preserving already-issued device sessions."""
    from apps.makerspaces.deployment_modules import mobile_module_enabled

    if not mobile_module_enabled():
        raise AuthenticationFailed("Mobile device sessions are not enabled.")


def token_fingerprint(raw):
    return hmac.new(settings.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()


@transaction.atomic
def issue_device_token_pair(user, grant, *, family=None):
    from apps.backup.recovery import assert_token_issuance_allowed
    from apps.accounts.surface_policy import assert_surface

    user = lock_token_issuance(user)
    assert_surface(user, "member")
    if grant.user_id != user.pk:
        raise AuthenticationFailed("Invalid device authorization.")
    assert_token_issuance_allowed(user)
    grant = DeviceGrant.objects.select_for_update().filter(pk=grant.pk, user=user).first()
    if (grant is None or grant.status != grant.Status.ACTIVE
            or grant.registration.status != NativeAppRegistration.Status.APPROVED):
        raise AuthenticationFailed("Invalid device authorization.")
    if family is not None:
        family = DeviceRefreshFamily.objects.select_for_update().get(pk=family.pk)
        if family.revoked_at or family.user_id != user.pk or family.grant_id != grant.pk:
            raise AuthenticationFailed("Invalid device authorization.")
    family = family or DeviceRefreshFamily.objects.create(grant=grant, user=user)
    refresh = SpaceWorksRefreshToken.for_user(user, web_session=False)
    refresh["surface"] = "member"
    refresh["device_grant_id"] = str(grant.pk)
    refresh["device_family_id"] = str(family.pk)
    raw = str(refresh)
    DeviceRefreshToken.objects.create(
        family=family,
        jti=refresh["jti"],
        token_fingerprint=token_fingerprint(raw),
        expires_at=datetime.fromtimestamp(refresh["exp"], tz=timezone.get_current_timezone()),
    )
    return str(refresh.access_token), raw, family


def rotate_device_refresh(raw):
    try:
        claims = UntypedToken(raw)
    except TokenError as exc:
        raise AuthenticationFailed("Invalid device refresh token.") from exc
    if claims.get("token_type") != "refresh":
        raise AuthenticationFailed("Invalid device refresh token.")
    jti = claims.get("jti")
    family_id = claims.get("device_family_id")
    grant_id = claims.get("device_grant_id")
    if not all((jti, family_id, grant_id)):
        raise AuthenticationFailed("Invalid device refresh token.")

    replay = False
    result = None
    with transaction.atomic():
        owner_id = DeviceRefreshToken.objects.filter(
            jti=jti, token_fingerprint=token_fingerprint(raw),
        ).values_list("family__user_id", flat=True).first()
        if owner_id is None:
            raise AuthenticationFailed("Invalid device refresh token.")
        try:
            user = User.objects.select_for_update(no_key=True).get(pk=owner_id)
        except User.DoesNotExist as exc:
            raise AuthenticationFailed("Invalid device refresh token.") from exc
        row = (
            DeviceRefreshToken.objects.select_for_update(of=("self",))
            .select_related("family__grant__registration", "family__user")
            .filter(jti=jti, token_fingerprint=token_fingerprint(raw))
            .first()
        )
        if row is None or str(row.family_id) != str(family_id):
            raise AuthenticationFailed("Invalid device refresh token.")
        family, grant = row.family, row.family.grant
        from apps.accounts.surface_policy import validate_account_token
        validate_account_token(user, claims)
        if user.account_kind != "member" or grant.user_id != user.pk:
            raise AuthenticationFailed("Invalid device refresh token.")
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
            or user.access_status != user.AccessStatus.ACTIVE
        ):
            blacklist_device_family(family, revoke_grant=True)
        elif (
            grant.status != grant.Status.ACTIVE
            or grant.registration.status != NativeAppRegistration.Status.APPROVED
        ):
            blacklist_device_family(family)
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
        raise AuthenticationFailed("Invalid device refresh token.")
    if result is None:
        raise AuthenticationFailed("Device authorization is no longer active.")
    return result
