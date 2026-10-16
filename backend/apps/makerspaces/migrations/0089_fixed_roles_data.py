"""Stopped-writer upgrade: snapshot, refuse unsafe rules, project, then mutate.

Irreversible once anything relies on the fixed catalogue (see fixed_roles_reverse);
restore the pre-upgrade backup to roll back.
"""

from django.db import migrations
from django.utils import timezone

from apps.makerspaces.migration_support.fixed_roles_catalogue import canonicalize_roles
from apps.makerspaces.migration_support.fixed_roles_projection import build_projection, refusal_message
from apps.makerspaces.migration_support.fixed_roles_reverse import reverse_fixed_roles
from apps.makerspaces.migration_support.fixed_roles_snapshot import PRE_SCHEMA_FIELDS, read_snapshot


def forwards(apps, schema_editor):
    connection = schema_editor.connection
    alias = connection.alias
    models = {label: apps.get_model(label) for label in PRE_SCHEMA_FIELDS}
    for label in (
        "makerspaces.MembershipAdditionalRole", "machines.MembershipMachineTypeScope",
        "audit.AuditLog", "audit.AuditMacKey",
    ):
        models[label] = apps.get_model(label)
    snapshot = read_snapshot(models, connection)
    projection = build_projection(snapshot)
    if projection["refused_recipient_rules"]:
        raise RuntimeError(refusal_message(projection["refused_recipient_rules"]))

    # Delayed import: the refusal path neither writes nor needs audit configuration.
    from apps.makerspaces.migration_support.fixed_roles_writes import (
        migrate_memberships, migrate_references,
    )

    role_model = models["makerspaces.MakerspaceRole"]
    canonical_ids = canonicalize_roles(role_model, alias, snapshot, projection["obsolete_role_ids"])
    migrate_memberships(models, alias, projection, canonical_ids)
    migrate_references(models, alias, projection, canonical_ids, timezone.now())
    # PROTECT references have all been repointed; obsolete role scopes cascade only
    # now, after their type links and original machine-id evidence were preserved.
    role_model.objects.using(alias).filter(pk__in=projection["obsolete_role_ids"]).delete()


def backwards(apps, schema_editor):
    reverse_fixed_roles(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ("makerspaces", "0088_fixed_roles_schema"),
        ("machines", "0027_membership_machine_type_scope"),
        ("accounts", "0026_mfa_staff_invitations"),
        ("integrations", "0030_notification_timing_policy"),
        ("operations", "0013_stocktake_discipline"),
        ("audit", "0009_audit_verification_runs"),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
