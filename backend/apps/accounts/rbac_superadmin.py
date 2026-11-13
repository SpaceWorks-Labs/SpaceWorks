"""Superadmin identity helpers for RBAC.

The superadmin holds global authority in every servable makerspace (owner decision
#110): no per-space switch withholds it. Archived and otherwise unservable spaces
are still excluded, by the servability policy in ``rbac``.

This path is pinned by ``tenant_migration.authority_guards.AUTHORIZATION_SOURCES``;
keep the file here even though it is now small.
"""

from apps.accounts.models import User


def _id_in(makerspace_id, ids):
    if makerspace_id in ids:
        return True
    try:
        return int(makerspace_id) in ids
    except (TypeError, ValueError):
        return False


def _is_superadmin(actor):
    return bool(
        actor is not None
        and getattr(actor, "is_authenticated", False)
        and not getattr(actor, "is_tenant_dump_stub", False)
        and (actor.is_superuser or actor.role == User.Role.SUPERADMIN)
    )
