"""Retain staff primary keys for immutable audit provenance, without an identity."""

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from django.db import connections
from django.utils import timezone

from apps.accounts.credential_revocation import revoke_all_credentials
from apps.accounts.models import User, UserMFA


def shell_values(user_id, retired_at):
    return {
        "username": f"retired-{uuid5(NAMESPACE_URL, f'spaceworks:retired-staff:{user_id}')}",
        "first_name": "", "last_name": "", "display_name": "", "email": "",
        "phone": "", "phone_e164": "", "telegram_user_id": "",
        "external_checkin_user_id": "", "restriction_reason": "",
        "email_verified_at": None, "phone_verified_at": None,
        "self_registered_at": None, "last_login": None,
        "date_joined": datetime(1970, 1, 1, tzinfo=UTC), "credential_generation": 0,
        "password": "!retired-staff", "is_active": False,
        "is_superuser": False, "is_staff": False, "is_walk_in": False,
        "is_tenant_dump_stub": False, "role": "requester", "access_status": "suspended",
        "must_change_password": True, "staff_makerspace_id": None, "retired_at": retired_at,
    }


def retire_staff_accounts(makerspace, *, actor=None):
    """Caller owns the tenant lock and transaction; revoke before locking User."""
    using = makerspace._state.db or "default"
    users = User.objects.using(using).filter(
        account_kind=User.AccountKind.STAFF, staff_makerspace=makerspace,
        retired_at__isnull=True,
    ).order_by("pk")
    with connections[using].cursor() as cursor:
        cursor.execute("SELECT set_config('app.account_retirement_makerspace_id', %s, true)",
                       [str(makerspace.pk)])
    for user in users:
        revoke_all_credentials(user, reason="makerspace_purge", actor=actor)
        UserMFA.objects.using(using).filter(user=user).delete()
        User.objects.using(using).filter(pk=user.pk).update(**shell_values(user.pk, timezone.now()))
