"""Decision 242(m): seed the Fundraising role into every existing makerspace.

New spaces get it from `roles.ensure_default_roles` (the role catalogue). This only adds the role
ROW: no membership is created or changed, so nobody's authority moves. The grant is frozen here
rather than read from the live catalogue, so a later catalogue edit cannot rewrite history.
"""

from django.db import migrations

SLUG = "fundraising"
ACTIONS = ["manage_donations"]


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    Role = apps.get_model("makerspaces", "MakerspaceRole")
    present = set(Role.objects.using(alias).filter(slug=SLUG).values_list("makerspace_id", flat=True))
    Role.objects.using(alias).bulk_create([
        Role(makerspace_id=pk, slug=SLUG, name="Fundraising", legacy_role=SLUG, granted_actions=ACTIONS,
             is_default=True, is_protected=True)
        for pk in Makerspace.objects.using(alias).exclude(pk__in=present).values_list("pk", flat=True)
    ], batch_size=500)


def unseed(apps, schema_editor):
    # PROTECT on memberships refuses this while anyone still holds the role.
    apps.get_model("makerspaces", "MakerspaceRole").objects.using(
        schema_editor.connection.alias).filter(slug=SLUG).delete()


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0141_fundraising_role_schema")]
    operations = [migrations.RunPython(seed, unseed)]
