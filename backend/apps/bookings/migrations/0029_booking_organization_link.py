"""Decision 223 (k), lane L3b: the organization a partner-event booking was made for."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("makerspaces", "0137_guest_passes"),
        ("organizations", "0008_invitation_email_digest"),
        ("bookings", "0028_booking_is_house"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingOrganizationLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization_name", models.CharField(max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("billed_member", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
                ("booking", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="organization_link",
                    to="bookings.booking")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
                ("organization", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to="organizations.organization")),
            ],
            options={"indexes": [models.Index(fields=["makerspace", "organization"], name="booking_org_link_idx")]},
        ),
    ]
