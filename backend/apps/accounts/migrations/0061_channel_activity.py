"""Web-session activity days and channel/area usage counts (analytics by channel)."""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0060_email_challenge_requested_handle"),
        ("makerspaces", "0093_fixed_roles_constraint"),
    ]

    operations = [
        migrations.AddField("deviceactivityday", "app_version", models.CharField(blank=True, default="", max_length=32)),
        migrations.CreateModel(name="WebSessionActivityDay", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ("session_hash", models.CharField(max_length=32)),
            ("makerspace", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, to="makerspaces.makerspace")),
            ("local_day", models.DateField()),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ], options={"constraints": [models.UniqueConstraint(
            fields=["user", "session_hash", "makerspace", "local_day"], nulls_distinct=False,
            name="unique_web_session_space_activity_day")]}),
        migrations.CreateModel(name="ChannelUsageDay", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("channel", models.CharField(max_length=16)),
            ("area", models.CharField(max_length=48)),
            ("makerspace", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, to="makerspaces.makerspace")),
            ("day", models.DateField()),
            ("count", models.PositiveBigIntegerField(default=0)),
        ], options={"constraints": [models.UniqueConstraint(
            fields=["channel", "area", "makerspace", "day"], nulls_distinct=False,
            name="unique_channel_area_space_day")]}),
    ]
