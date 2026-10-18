"""Native access checks and the short User -> DeviceGrant heartbeat transaction."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import User
from apps.accounts.models_devices import DeviceGrant, DeviceRefreshFamily
from apps.accounts.native_app_identity import registration_is_eligible
from apps.accounts.session_issuance import lock_session_user, validate_session_generation


def validated_device_grant(user, token, *, lock=False):
    try:
        grants = DeviceGrant.objects.select_related("registration")
        if lock:
            grants = grants.select_for_update(of=("self",))
        grant = grants.filter(pk=token["device_grant_id"], user=user).first()
        valid = bool(
            grant and grant.status == DeviceGrant.Status.ACTIVE
            and grant.revoked_at is None
            and registration_is_eligible(grant.registration)
            and user.is_active and user.access_status == User.AccessStatus.ACTIVE
            and grant.authority == user.account_kind
            and grant.credential_generation == user.credential_generation
            and grant.staff_makerspace_id == user.staff_makerspace_id
            and (user.account_kind != "staff" or grant.login_method == "password")
            and (user.account_kind != "staff" or grant.registration.makerspace_id in (None, user.staff_makerspace_id))
            and DeviceRefreshFamily.objects.filter(
                pk=token["device_family_id"], grant=grant, user=user, revoked_at__isnull=True,
            ).exists()
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise AuthenticationFailed("Invalid device authorization.") from exc
    if not valid:
        raise AuthenticationFailed("Device authorization is no longer active.")
    return grant


@transaction.atomic
def heartbeat_device_grant(user, token):
    # The grant UPDATE trigger locks User too. Own User first, just as logout-all,
    # recovery and deletion do, then recheck authority after any lock wait.
    user = lock_session_user(user)
    validate_session_generation(user, token)
    grant = validated_device_grant(user, token, lock=True)
    DeviceGrant.objects.filter(pk=grant.pk).update(last_used_at=timezone.now())
    return grant
