from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0092_money_three_decimals")]

    operations = [
        migrations.AddField("eventcrewmember", "kind", models.CharField(
            blank=True, null=True, max_length=12,
            choices=[("organiser", "Organiser"), ("volunteer", "Volunteer"), ("mentor", "Mentor"), ("judge", "Judge")])),
        migrations.AddField("eventcrewmember", "position", models.PositiveIntegerField(default=0)),
        migrations.AddField("eventcrewmember", "staff_hidden", models.BooleanField(default=False)),
        migrations.AlterModelOptions("eventcrewmember", options={"ordering": ["event_id", "position", "pk"]}),
        migrations.AddField("hackathonteam", "deleted_at", models.DateTimeField(blank=True, null=True)),
        migrations.AddField("hackathonteam", "deleted_snapshot", models.JSONField(blank=True, default=dict)),
    ]
