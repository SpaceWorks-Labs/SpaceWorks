"""Only the fixed Space Manager gains the distinct payout recording action."""
from django.db import migrations

ACTION = "record_reimbursement_payout"


def change(apps, schema_editor, *, remove=False):
    Role = apps.get_model("makerspaces", "MakerspaceRole")
    roles = Role.objects.using(schema_editor.connection.alias).filter(
        slug="space_manager", is_default=True, is_protected=True,
    )
    for role in roles.iterator():
        actions = set(role.granted_actions)
        if remove:
            actions.discard(ACTION)
        else:
            actions.add(ACTION)
        role.granted_actions = sorted(actions)
        role.save(using=schema_editor.connection.alias, update_fields=["granted_actions"])


def forwards(apps, schema_editor):
    change(apps, schema_editor)


def backwards(apps, schema_editor):
    change(apps, schema_editor, remove=True)


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0105_remove_anonymous_requests_enabled")]
    operations = [migrations.RunPython(forwards, backwards)]
