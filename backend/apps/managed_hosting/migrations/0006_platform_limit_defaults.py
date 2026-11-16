import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("managed_hosting", "0005_platformhostingbillingsettings_plural"),
        ("makerspaces", "0131_makerspace_suspended_state"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformLimitDefault",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("value", models.PositiveBigIntegerField(
                    help_text="Whole units of the key (bytes for byte keys). Delete the row for no limit.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("key",)},
        ),
        migrations.CreateModel(
            name="SpaceLimitThreshold",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64)),
                ("level", models.PositiveSmallIntegerField(
                    help_text="80 or 100: the highest threshold already notified.")),
                ("notified_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="limit_thresholds", to="makerspaces.makerspace")),
            ],
        ),
        migrations.AddConstraint(
            model_name="spacelimitthreshold",
            constraint=models.UniqueConstraint(fields=("makerspace", "key"), name="space_limit_threshold_once"),
        ),
    ]
