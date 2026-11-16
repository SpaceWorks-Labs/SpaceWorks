from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import apps.bookings.booking_permissions
import apps.makerspaces.resource_grants_models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0011_calendar_feed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingSpaceStaffGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("permissions", models.JSONField(validators=[apps.bookings.booking_permissions.validate_permissions])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("space", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_rows", to="bookings.bookablespace")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="makerspaces.makerspace")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookings_staff_grants", to=settings.AUTH_USER_MODEL)),
                ("granted_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("user", "space"), condition=models.Q(revoked_at__isnull=True), name="booking_staff_grant_active_space"),
            ]},
        ),
        migrations.CreateModel(
            name="BookingSpaceStaffGrantInvite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("permissions", models.JSONField(validators=[apps.bookings.booking_permissions.validate_permissions])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("space", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)s_rows", to="bookings.bookablespace")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="makerspaces.makerspace")),
                ("token_digest", models.CharField(editable=False, max_length=64, unique=True)),
                ("email_digest", models.CharField(blank=True, default="", editable=False, max_length=64)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("expires_at", models.DateTimeField(default=apps.makerspaces.resource_grants_models.invite_expiry)),
                ("redeemed_at", models.DateTimeField(blank=True, null=True)),
                ("redeemed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
            ]},
        ),
    ]
