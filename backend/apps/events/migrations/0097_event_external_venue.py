from django.db import migrations, models

import apps.events.venue


class Migration(migrations.Migration):
    """Decision 295: an external venue address and https map link on events and series templates."""

    dependencies = [("events", "0096_submission_stage_ceiling")]

    operations = [
        migrations.AddField(model_name=model, name=name, field=field)
        for model in ("event", "eventseries")
        for name, field in (
            ("venue_address", models.CharField(blank=True, default="", max_length=500)),
            ("venue_map_url", models.CharField(blank=True, default="", max_length=500,
                                               validators=[apps.events.venue.validate_map_url])),
        )
    ]
