"""makerspaces/0111: fold the retired module keys, and grant today's settings editors.

Kept here, outside `migrations/`, so the audit discovery guards read its literal actions and
meta like every other emitter (the migration writer has the same positions as audit.record).
Historical models only; the rules are frozen copies on purpose.
"""

from apps.makerspaces.migration_support.fixed_roles_audit import record

SOURCE = "migration:makerspaces.0111"
MANAGER_ACTIONS = {
    "events": "manage_events", "bookings": "manage_bookings",
    "machines": "manage_machines", "inventory": "edit_inventory",
}
ORG_GRANTABLE = {"manage_events", "manage_bookings", "edit_inventory"}
COMBINABLE = {"inventory_manager", "machine_manager", "event_manager", "booking_manager", "handover"}


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
            record(space.pk, "makerspace.module_retired", "makerspaces.makerspace", space.pk,
                   models=models, alias=alias,
                   meta={"module": key, "capabilities": added.get(key, []), "source": SOURCE})
        if added["warranty"]:
            record(space.pk, "makerspace.capabilities_changed", "makerspaces.makerspace", space.pk,
                   models=models, alias=alias,
                   meta={"source": SOURCE, "added_features": added["warranty"],
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
            record(space_id, "settings.grant_created", "makerspaces.modulesettingsgrant", row.pk,
                   models=models, alias=alias,
                   meta={"module": module, "grant_id": row.pk, "via": "migration", "source": SOURCE})


def forwards(apps, schema_editor):
    fold(apps, schema_editor)
    grant(apps, schema_editor)


