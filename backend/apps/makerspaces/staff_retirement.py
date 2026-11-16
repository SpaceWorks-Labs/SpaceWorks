"""Inert-shell identity values: keep a primary key for immutable history, without an identity.

Used for legacy retired-staff shells in backup projections and, with a ``merged-<uuid>``
username, by the account-merge engine. Since one account per person, a tenant purge
retires nobody: people keep their accounts and only the tenant's rows go.
"""

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5


def shell_values(user_id, retired_at):
    return {
        "username": f"retired-{uuid5(NAMESPACE_URL, f'spaceworks:retired-staff:{user_id}')}",
        "first_name": "", "last_name": "", "display_name": "", "email": "",
        "phone": "", "phone_e164": "", "telegram_user_id": "",
        "restriction_reason": "",
        "email_verified_at": None, "phone_verified_at": None,
        "self_registered_at": None, "last_login": None,
        "date_joined": datetime(1970, 1, 1, tzinfo=UTC), "credential_generation": 0,
        "password": "!retired-staff", "is_active": False,
        "is_superuser": False, "is_staff": False, "is_walk_in": False,
        "is_tenant_dump_stub": False, "role": "requester", "access_status": "suspended",
        "must_change_password": True, "staff_makerspace_id": None, "retired_at": retired_at,
    }
