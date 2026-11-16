"""Membership now requires member accounts (owner decision #91): repair existing rows.

A space that already has `membership` without `member_accounts` gets member accounts
turned on, with an audit entry per space (`makerspace.capabilities_changed`, written by
the migration-safe audit writer so the row MAC matches a live entry). Without this the
space would sit in a state the registry now forbids, and its borrow-request policy
would silently become the account-less contact path (#80) despite having members.

Not reversed: switching member accounts back off is an operator decision made in
/control/, where completion also unticks membership.
"""

from django.db import migrations

MEMBERSHIP = "membership"
MEMBER_ACCOUNTS = "member_accounts"


def repair(apps, schema_editor):
    from apps.makerspaces.migration_support.fixed_roles_audit import record

    alias = schema_editor.connection.alias
    models = {label: apps.get_model(label) for label in ("audit.AuditLog", "audit.AuditMacKey")}
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for space in Makerspace.objects.using(alias).only("id", "enabled_modules").order_by("pk"):
        modules = list(space.enabled_modules or [])
        if MEMBERSHIP not in modules or MEMBER_ACCOUNTS in modules:
            continue
        space.enabled_modules = sorted({*modules, MEMBER_ACCOUNTS})
        space.save(update_fields=["enabled_modules"])
        record(
            space.pk, "makerspace.capabilities_changed", "makerspaces.makerspace", space.pk,
            models=models, alias=alias,
            meta={"source": "migration:makerspaces.0108", "added_modules": [MEMBER_ACCOUNTS],
                  "reason": "membership requires member_accounts (owner decision #91)"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0107_delight_on_by_default"),
        ("audit", "0009_audit_verification_runs"),
    ]
    operations = [migrations.RunPython(repair, migrations.RunPython.noop)]
