"""Native access checks and the short User -> DeviceGrant heartbeat transaction."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import User
from apps.accounts.models_devices import DeviceGrant, DeviceRefreshFamily
from apps.accounts.native_app_identity import registration_is_eligible
from apps.accounts.session_issuance import lock_session_user, validate_session_generation
from apps.accounts.staff_identity import is_person


def validated_device_grant(user, token, *, lock=False):
    try:
        grants = DeviceGrant.objects.select_related("registration")
        if lock:
            grants = grants.select_for_update(of=("self",))
        grant = grants.filter(pk=token["device_grant_id"], user=user).first()
        staff = bool(grant and grant.authority == DeviceGrant.Authority.STAFF)
        valid = bool(
            grant and grant.status == DeviceGrant.Status.ACTIVE
            and grant.revoked_at is None
            and registration_is_eligible(grant.registration)
            and is_person(user)
            and user.is_active and user.access_status == User.AccessStatus.ACTIVE
            and grant.credential_generation == user.credential_generation
            and (not staff or grant.staff_makerspace_id is not None)
            and DeviceRefreshFamily.objects.filter(
                pk=token["device_family_id"], grant=grant, user=user, revoked_at__isnull=True,
            ).exists()
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise AuthenticationFailed(gettext("Invalid device authorization.")) from exc
    if valid and staff:
        # A staff grant lives only as long as the staff role it stepped up to. Outside the
        # heartbeat lock, a lost role is revoked (its own transaction) before refusing.
        from apps.accounts.services_staff_grants import ACTIVE, revoke_if_role_lost, staff_role_state
        state = staff_role_state(user, grant.staff_makerspace_id) if lock else revoke_if_role_lost(
            user, grant.staff_makerspace_id)
        valid = state == ACTIVE
    if valid and grant.authority == DeviceGrant.Authority.EVENT:
        # #173: an event grant lives only as long as the event role it stepped up to.
        from apps.accounts.services_event_grants import ACTIVE as EVENT_ACTIVE, event_role_state, revoke_if_event_role_lost
        state = event_role_state(user, grant.event_id) if lock else revoke_if_event_role_lost(user, grant.event_id)
        valid = state == EVENT_ACTIVE
    if not valid:
        raise AuthenticationFailed(gettext("Device authorization is no longer active."))
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
