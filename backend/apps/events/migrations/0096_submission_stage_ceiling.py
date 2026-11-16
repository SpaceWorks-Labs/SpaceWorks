"""Decision 296 addendum [auto, 243]: an organiser may plan up to 50 submission stages.

The old ceiling (10) was a hard CHECK constraint. The per-space ``hackathon_stages`` limit
(decision 284; unset = no limit) lowers it per space at the service layer, never in the database.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("events", "0095_search_vector_tags_org")]

    operations = [
        migrations.RemoveConstraint(model_name="submissionstage", name="ev_stage_position_range"),
        migrations.AddConstraint(
            model_name="submissionstage",
            constraint=models.CheckConstraint(condition=models.Q(("position__gte", 1), ("position__lte", 50)),
                                              name="ev_stage_position_range"),
        ),
    ]
