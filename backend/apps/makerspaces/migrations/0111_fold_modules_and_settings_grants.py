"""Fold the retired module keys into per-parent capabilities, and grant today's editors.

Owner decisions #97, #128 C-9 and C-11b. Every space keeps exactly what it had:

* `maintenance` installed -> `machines.maintenance` on;
* `procurement` installed -> `inventory.tobuy` on, and `machines.tobuy` on where
  `machines` is installed (today's To-Buy list covers both kinds);
* warranty rows on assets -> `inventory.warranty`; on machines (with `machines`
  installed) -> `machines.warranty`;
* the two old keys are stripped from `enabled_modules`; no row of any table is touched.
  Each retired key is audited per space as `makerspace.module_retired`.

Then every person who could edit a domain's settings through `domain_settings` -- an
active membership (or active organization grant) holding that domain's manager action,
without `manage_makerspace` -- receives a per-person grant, audited as
`settings.grant_created` with `via=migration`. New spaces start with no grants.

The rules below are frozen copies on purpose: a migration must not follow later edits of
the live registries. Not reversed: switching capabilities back is an operator decision.
"""

from django.db import migrations

SOURCE = "migration:makerspaces.0111"
MANAGER_ACTIONS = {
    "events": "manage_events", "bookings": "manage_bookings",
    "machines": "manage_machines", "inventory": "edit_inventory",
}
ORG_GRANTABLE = {"manage_events", "manage_bookings", "edit_inventory"}
COMBINABLE = {"inventory_manager", "machine_manager", "event_manager", "booking_manager", "handover"}


def _audit(models, alias, space_id, action, target_type, target_id, meta):
    from apps.makerspaces.migration_support.fixed_roles_audit import record

    record(space_id, action, target_type, target_id, models=models, alias=alias, meta=meta)


def folded_capabilities(apps, alias, space):
    Warranty = apps.get_model("warranty", "Warranty")
    modules = set(space.enabled_modules or [])
    added = {}
    if "maintenance" in modules:
        added["maintenance"] = ["machines.maintenance"]
    if "procurement" in modules:
        added["procurement"] = ["inventory.tobuy"] + (["machines.tobuy"] if "machines" in modules else [])
    warranties = Warranty.objects.using(alias).filter(makerspace_id=space.pk)
    added["warranty"] = (
        (["inventory.warranty"] if warranties.filter(asset__isnull=False).exists() else [])
        + (["machines.warranty"] if "machines" in modules and warranties.filter(machine__isnull=False).exists() else [])
    )
    return added


def fold(apps, schema_editor):
    alias = schema_editor.connection.alias
    models = {label: apps.get_model(label) for label in ("audit.AuditLog", "audit.AuditMacKey")}
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.using(alias).order_by("pk"):
        added = folded_capabilities(apps, alias, space)
        modules = list(space.enabled_modules or [])
        features = set(space.enabled_features or [])
        new_features = {key for keys in added.values() for key in keys} - features
        retired = [key for key in ("maintenance", "procurement") if key in modules]
        if not retired and not new_features:
            continue
        space.enabled_modules = [key for key in modules if key not in {"maintenance", "procurement"}]
        space.enabled_features = sorted(features | new_features)
        space.save(update_fields=["enabled_modules", "enabled_features"])
        for key in retired:
            _audit(models, alias, space.pk, "makerspace.module_retired", "makerspaces.makerspace", space.pk,
                   {"module": key, "capabilities": added.get(key, []), "source": SOURCE})
        if added["warranty"]:
            _audit(models, alias, space.pk, "makerspace.capabilities_changed", "makerspaces.makerspace", space.pk,
                   {"source": SOURCE, "added_features": added["warranty"],
                    "reason": "warranty rows exist (owner decision #97)"})


def _membership_actions(apps, alias, membership):
    Additional = apps.get_model("makerspaces", "MembershipAdditionalRole")
    primary = membership.assigned_role
    if primary is None or primary.makerspace_id != membership.makerspace_id:
        return set()
    roles = [primary]
    if primary.slug in COMBINABLE:
        roles += [link.role for link in Additional.objects.using(alias).filter(membership=membership).select_related("role")
                  if link.role.makerspace_id == membership.makerspace_id and link.role.slug in COMBINABLE]
    return {action for role in roles if isinstance(role.granted_actions, list)
            for action in role.granted_actions if isinstance(action, str)}


def editors(apps, alias):
    """{(makerspace_id, module): {user_id}} for everyone who edits domain settings today."""
    Membership = apps.get_model("makerspaces", "MakerspaceMembership")
    OrgMembership = apps.get_model("organizations", "OrganizationMembership")
    Link = apps.get_model("organizations", "OrganizationMakerspace")
    result, managers = {}, set()
    for membership in Membership.objects.using(alias).filter(
            status="active", user__is_active=True).select_related("assigned_role").order_by("pk"):
        actions = _membership_actions(apps, alias, membership)
        if "manage_makerspace" in actions:
            managers.add((membership.makerspace_id, membership.user_id))
            continue
        for module, action in MANAGER_ACTIONS.items():
            if action in actions:
                result.setdefault((membership.makerspace_id, module), set()).add(membership.user_id)
    links = {}
    for link in Link.objects.using(alias).all():
        links.setdefault(link.organization_id, set()).add(link.makerspace_id)
    for row in OrgMembership.objects.using(alias).filter(
            status="active", organization__is_active=True, user__is_active=True).order_by("pk"):
        actions = set(row.granted_actions) if isinstance(row.granted_actions, list) else set()
        for module, action in MANAGER_ACTIONS.items():
            if action in ORG_GRANTABLE and action in actions:
                for space_id in links.get(row.organization_id, ()):
                    result.setdefault((space_id, module), set()).add(row.user_id)
    return {key: users - {user for space, user in managers if space == key[0]} for key, users in result.items()}


def grant(apps, schema_editor):
    alias = schema_editor.connection.alias
    models = {label: apps.get_model(label) for label in ("audit.AuditLog", "audit.AuditMacKey")}
    Grant = apps.get_model("makerspaces", "ModuleSettingsGrant")
    for (space_id, module), users in sorted(editors(apps, alias).items()):
        for user_id in sorted(users):
            if Grant.objects.using(alias).filter(makerspace_id=space_id, module=module, grantee_id=user_id,
                                                 revoked_at__isnull=True).exists():
                continue
            row = Grant.objects.using(alias).create(makerspace_id=space_id, module=module, grantee_id=user_id)
            _audit(models, alias, space_id, "settings.grant_created", "makerspaces.modulesettingsgrant", row.pk,
                   {"module": module, "grant_id": row.pk, "via": "migration", "source": SOURCE})


def forwards(apps, schema_editor):
    fold(apps, schema_editor)
    grant(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0110_settings_authority"),
        ("audit", "0009_audit_verification_runs"),
        ("organizations", "0007_events_programme_schema"),
        ("warranty", "0003_remove_printer_host"),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
