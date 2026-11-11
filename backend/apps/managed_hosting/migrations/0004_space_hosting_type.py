import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def existing_spaces_are_own(apps, schema_editor):
    """Decision 236: every space that exists before this release is the operator's own."""
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    SpaceHostingType = apps.get_model("managed_hosting", "SpaceHostingType")
    SpaceHostingType.objects.bulk_create(
        [SpaceHostingType(makerspace_id=pk, hosting_type="own") for pk in Makerspace.objects.values_list("pk", flat=True)],
        ignore_conflicts=True, batch_size=500,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("managed_hosting", "0003_platform_throttle_rate"),
        ("makerspaces", "0131_makerspace_suspended_state"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SpaceHostingType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("hosting_type", models.CharField(choices=[("own", "Own space"), ("hosted", "Hosted space")],
                                                  default="own", max_length=8)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                    related_name="hosting_type_row", to="makerspaces.makerspace")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(existing_spaces_are_own, migrations.RunPython.noop),
    ]
