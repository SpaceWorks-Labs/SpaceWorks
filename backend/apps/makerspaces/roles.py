"""Seed and synchronize per-makerspace instances of the fixed role catalogue."""

from .role_catalog import ROLE_CATALOG


# Preserve the tuple shapes consumed by bootstrap code and existing callers.
DEFAULT_ROLE_DEFINITIONS = tuple(
    (role.legacy_role, role.name, sorted(role.granted_actions))
    for role in ROLE_CATALOG if role.slug != "member"
)
_member = next(role for role in ROLE_CATALOG if role.slug == "member")
MEMBER_ROLE_DEFINITION = (_member.legacy_role, _member.name, sorted(_member.granted_actions), _member.slug)


def ensure_default_roles(makerspace):
    """Restore canonical grants, labels and flags as well as creating missing rows."""
    from django.db import transaction

    from apps.makerspaces.models import MakerspaceRole

    alias = makerspace._state.db or "default"
    with transaction.atomic(using=alias):
        roles = MakerspaceRole.objects.using(alias).filter(makerspace=makerspace)
        existing = list(roles.values("id", "slug", "name"))
        names = {row["name"].casefold() for row in existing}
        canonical = {role.slug: role.name for role in ROLE_CATALOG}
        roles.filter(slug__in=canonical).update(
            legacy_role=None, is_default=True, is_protected=True,
        )
        # Clear changed names together, so swapped administrator labels can also
        # be restored without violating the case-insensitive name constraint.
        for row in existing:
            if row["slug"] not in canonical or row["name"] == canonical[row["slug"]]:
                continue
            attempt = 0
            temporary = f"__fixed_role_sync_{row['id']}_{attempt}"
            while temporary.casefold() in names:
                attempt += 1
                temporary = f"__fixed_role_sync_{row['id']}_{attempt}"
            names.add(temporary.casefold())
            roles.filter(pk=row["id"]).update(name=temporary)
        for definition in ROLE_CATALOG:
            fields = {
                "name": definition.name,
                "legacy_role": definition.legacy_role,
                "granted_actions": sorted(definition.granted_actions),
                "is_default": True,
                "is_protected": True,
            }
            role, created = MakerspaceRole.objects.using(alias).get_or_create(
                makerspace=makerspace,
                slug=definition.slug,
                defaults=fields,
            )
            if not created:
                roles.filter(pk=role.pk).update(**fields)
