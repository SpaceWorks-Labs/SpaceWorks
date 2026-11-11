"""Open item B13: the organization hours allowance and its append-only ledger."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("makerspaces", "0137_guest_passes"),
        ("organizations", "0008_invitation_email_digest"),
        ("bookings", "0030_money_three_decimals"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationHoursAllowance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("allowance_minutes", models.PositiveIntegerField(default=0)),
                ("period", models.CharField(
                    choices=[("none", "One pool, never resets"), ("monthly", "Resets every calendar month"),
                             ("yearly", "Resets every calendar year")], default="none", max_length=8)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="organizations.organization")),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="organizationhoursallowance",
            constraint=models.UniqueConstraint(
                fields=("makerspace", "organization"), name="org_hours_allowance_one_per_org_space"),
        ),
        migrations.CreateModel(
            name="OrganizationHoursLedger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry", models.CharField(
                    choices=[("grant", "Granted"), ("consume", "Consumed by a booking"),
                             ("release", "Released from a booking"), ("adjust", "Adjusted")], max_length=8)),
                ("minutes", models.IntegerField()),
                ("period_key", models.CharField(max_length=8)),
                ("generation", models.PositiveIntegerField(default=1)),
                ("reason", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
                ("booking", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name="organization_hours", to="bookings.booking")),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="organizations.organization")),
                ("reverses", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="+",
                    to="bookings.organizationhoursledger")),
            ],
            options={
                "ordering": ["-created_at", "-pk"],
                "indexes": [models.Index(fields=["makerspace", "organization", "period_key"],
                                         name="org_hours_period_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="organizationhoursledger",
            constraint=models.CheckConstraint(condition=~models.Q(minutes=0), name="org_hours_minutes_nonzero"),
        ),
        migrations.AddConstraint(
            model_name="organizationhoursledger",
            constraint=models.CheckConstraint(
                condition=(models.Q(entry="consume", minutes__lt=0, booking__isnull=False, reverses__isnull=True)
                           | models.Q(entry="release", minutes__gt=0, booking__isnull=False, reverses__isnull=False)
                           | models.Q(entry="grant", minutes__gt=0, booking__isnull=True, reverses__isnull=True)
                           | models.Q(entry="adjust", booking__isnull=True, reverses__isnull=True)),
                name="org_hours_entry_shape"),
        ),
        migrations.AddConstraint(
            model_name="organizationhoursledger",
            constraint=models.UniqueConstraint(
                condition=models.Q(entry="consume"), fields=("makerspace", "booking", "generation"),
                name="org_hours_one_consume_per_generation"),
        ),
        migrations.AddConstraint(
            model_name="organizationhoursledger",
            constraint=models.UniqueConstraint(
                condition=models.Q(entry="release"), fields=("makerspace", "reverses"), name="org_hours_one_release"),
        ),
    ]
