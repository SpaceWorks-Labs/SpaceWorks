"""Release 2 L1 (#77): a "closed for now" banner on the public page; no new lifecycle state."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("makerspaces", "0111_fold_modules_and_settings_grants")]

    operations = [
        migrations.AddField(
            model_name="makerspace", name="public_closed_notice",
            field=models.CharField(blank=True, default="", max_length=280),
        ),
        migrations.AddField(
            model_name="makerspace", name="public_reopens_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]
