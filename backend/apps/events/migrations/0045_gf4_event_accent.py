from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0044_gf4_print_custody")]
    operations = [migrations.AddField(
        model_name="event", name="accent_preset",
        field=models.CharField(blank=True, default="", max_length=24, choices=[
            ("maker_teal", "Maker Teal"), ("workshop_orange", "Workshop Orange"),
            ("citron", "Citron"), ("sky_blue", "Sky Blue"), ("warm_yellow", "Warm Yellow"),
        ]),
    ), migrations.AddConstraint(model_name="event", constraint=models.CheckConstraint(
        condition=models.Q(accent_preset__in=("", "maker_teal", "workshop_orange", "citron", "sky_blue", "warm_yellow")),
        name="event_accent_palette_only",
    ))]
