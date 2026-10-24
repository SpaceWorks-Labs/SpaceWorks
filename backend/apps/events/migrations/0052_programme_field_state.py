import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """State-only: resolve 0037's "self" FK targets and its mis-encoded choice label."""

    dependencies = [
        ("events", "0051_gf4_pii_maintenance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="eventresultrevision",
            name="correction_of",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="+", to="events.eventresultrevision"),
        ),
        migrations.AlterField(
            model_name="judginground",
            name="mode",
            field=models.CharField(choices=[("weighted_1_5", "Weighted 1–5"), ("top3", "Top three")], max_length=16),
        ),
        migrations.AlterField(
            model_name="submissionsnapshot",
            name="amendment_of",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="+", to="events.submissionsnapshot"),
        ),
    ]
