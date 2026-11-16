from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import apps.events.event_permissions
import apps.makerspaces.resource_grants_models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0025_event_ticketing_and_audience"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventStaffGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("permissions", models.JSONField(validators=[apps.events.event_permissions.validate_permissions])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="makerspaces.makerspace")),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_rows", to="events.event")),
                ("series", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_rows", to="events.eventseries")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_staff_grants", to=settings.AUTH_USER_MODEL)),
                ("granted_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.CheckConstraint(condition=(models.Q(event__isnull=False, series__isnull=True) | models.Q(event__isnull=True, series__isnull=False)), name="event_staff_grant_one_target"),
                models.UniqueConstraint(fields=("user", "event"), condition=models.Q(revoked_at__isnull=True), name="event_staff_grant_active_event"),
                models.UniqueConstraint(fields=("user", "series"), condition=models.Q(revoked_at__isnull=True), name="event_staff_grant_active_series"),
            ]},
        ),
        migrations.CreateModel(
            name="EventStaffGrantInvite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("permissions", models.JSONField(validators=[apps.events.event_permissions.validate_permissions])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="makerspaces.makerspace")),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_rows", to="events.event")),
                ("series", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_rows", to="events.eventseries")),
                ("token_digest", models.CharField(editable=False, max_length=64, unique=True)),
                ("email_digest", models.CharField(blank=True, default="", editable=False, max_length=64)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("expires_at", models.DateTimeField(default=apps.makerspaces.resource_grants_models.invite_expiry)),
                ("redeemed_at", models.DateTimeField(blank=True, null=True)),
                ("redeemed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.CheckConstraint(condition=(models.Q(event__isnull=False, series__isnull=True) | models.Q(event__isnull=True, series__isnull=False)), name="event_staff_invite_one_target"),
            ]},
        ),
    ]
