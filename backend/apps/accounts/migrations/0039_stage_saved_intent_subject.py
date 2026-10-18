"""Add the separate Saved-details stage subject; the age enum stays closed."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0038_events_programme_schema")]
    operations = [
        migrations.RemoveConstraint(model_name="saveddetailupdateintent", name="saved_intent_subject_kind"),
        migrations.AddConstraint(
            model_name="saveddetailupdateintent",
            constraint=models.CheckConstraint(
                condition=models.Q(subject_kind__in=["registration", "application", "role_assignment", "stage_response"]),
                name="saved_intent_subject_kind",
            ),
        ),
    ]
