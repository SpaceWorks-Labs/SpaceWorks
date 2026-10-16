"""Narrow target-owned rows created after the raw makerspace root is inserted."""

from django.apps import apps
from django.db import connections
from django.utils import timezone

from apps.makerspaces.roles import DEFAULT_ROLE_DEFINITIONS, MEMBER_ROLE_DEFINITION

from .tenant_dump_errors import TenantDumpVerificationError


def seed_default_roles(using, makerspace_id):
    """Seed current protected defaults without invoking model save/signals."""
    model = apps.get_model("makerspaces.MakerspaceRole")
    connection = connections[using]
    quote = connection.ops.quote_name
    table = quote(model._meta.db_table)
    actions_field = model._meta.get_field("granted_actions")
    now = timezone.now()
    role_ids = {}
    definitions = (*DEFAULT_ROLE_DEFINITIONS, MEMBER_ROLE_DEFINITION)
    with connection.cursor() as cursor:
        for legacy_role, name, actions, *slug_parts in definitions:
            slug = slug_parts[0] if slug_parts else legacy_role
            cursor.execute(
                f"INSERT INTO {table} "
                "(makerspace_id, name, slug, granted_actions, legacy_role, "
                "is_default, is_protected, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, TRUE, TRUE, %s, %s) "
                f"RETURNING {quote(model._meta.pk.column)}",
                [
                    makerspace_id,
                    name,
                    slug,
                    actions_field.get_db_prep_save(sorted(actions), connection),
                    legacy_role,
                    now,
                    now,
                ],
            )
            role_ids[slug] = cursor.fetchone()[0]
    if "member" not in role_ids:
        raise TenantDumpVerificationError("Target Member role was not seeded.")
    return role_ids
