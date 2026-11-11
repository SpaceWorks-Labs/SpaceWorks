# Final audit 0.12.0 (m22): Incident.involved_note is scoped PII, so it must be a TextField (ciphertext
# outgrows varchar(200)); the serializer keeps the 200-character input limit.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0009_incident_register"),
    ]

    operations = [
        migrations.AlterField(
            model_name="incident",
            name="involved_note",
            field=models.TextField(blank=True),
        ),
    ]
