from django.db import migrations, models


class Migration(migrations.Migration):
    """External QR labels: a source flag plus the value printed outside SpaceWorks.

    Every existing row is `spaceworks` with a blank external value, so the check
    constraint holds on old data and no backfill is needed.
    """

    dependencies = [
        ("boxes", "0012_plain_admin_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="qrcode",
            name="source",
            field=models.CharField(
                choices=[("spaceworks", "SpaceWorks"), ("external", "External")],
                default="spaceworks",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="qrcode",
            name="external_value",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddConstraint(
            model_name="qrcode",
            constraint=models.UniqueConstraint(
                condition=models.Q(source="external"),
                fields=("makerspace", "external_value"),
                name="uniq_external_qr_value_per_makerspace",
            ),
        ),
        migrations.AddConstraint(
            model_name="qrcode",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(source="spaceworks", external_value="")
                    | (models.Q(source="external") & ~models.Q(external_value=""))
                ),
                name="qr_external_value_matches_source",
            ),
        ),
    ]
