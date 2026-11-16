"""Decision 550: repair missing built-in Fundraising rows without moving authority.

0141/0142 already introduced the protected role. This leaf migration repairs older
spaces missing it; the audit records exactly which rows it inserted. Reversal leaves
pre-existing roles alone and PROTECT refuses reversal of a role now in use.
"""

from .fixed_roles_audit import record

SOURCE = "migration:makerspaces.0156"
LABELS = ("makerspaces.Makerspace", "makerspaces.MakerspaceRole", "audit.AuditLog", "audit.AuditMacKey")


def forwards(apps, schema_editor):
    alias = schema_editor.connection.alias
    models = {label: apps.get_model(label) for label in LABELS}
    Role = models["makerspaces.MakerspaceRole"]
    for space_id in models["makerspaces.Makerspace"].objects.using(alias).values_list("pk", flat=True).iterator():
        role, created = Role.objects.using(alias).get_or_create(
            makerspace_id=space_id, slug="fundraising", defaults={
                "name": "Fundraising", "legacy_role": "fundraising", "granted_actions": ["manage_donations"],
                "is_default": True, "is_protected": True,
            })
        if created:
            record(space_id, "staff.roles_migrated", "makerspaces.makerspacerole", role.pk,
                   models=models, alias=alias, meta={"source": SOURCE, "role_id": role.pk,
                                                   "to_roles": ["fundraising"], "direction": "forward"})


def backwards(apps, schema_editor):
    alias = schema_editor.connection.alias
    models = {label: apps.get_model(label) for label in LABELS}
    rows = models["audit.AuditLog"].objects.using(alias).filter(
        action="staff.roles_migrated", meta__source=SOURCE, meta__direction="forward")
    for row in rows.iterator():
        roles = models["makerspaces.MakerspaceRole"].objects.using(alias).filter(
            pk=row.meta["role_id"], makerspace_id=row.makerspace_id, slug="fundraising")
        if roles.exists():
            roles.delete()
            record(row.makerspace_id, "staff.roles_migrated", "makerspaces.makerspacerole", row.meta["role_id"],
                   models=models, alias=alias, meta={"source": SOURCE, "role_id": row.meta["role_id"],
                                                   "to_roles": [], "direction": "reverse"})
