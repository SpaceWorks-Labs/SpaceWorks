"""Schema first: references can be populated before the catalogue constraint."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ROLE_CHOICES = [
    ("space_manager", "Space Manager"), ("inventory_manager", "Inventory Manager"),
    ("print_manager", "Print Manager"), ("machine_manager", "Machine Manager"),
    ("event_manager", "Event Manager"), ("booking_manager", "Booking Manager"),
    ("handover", "Handover"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0087_remove_in_app_updates"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="makerspacemembership", name="role",
            field=models.CharField(choices=[*ROLE_CHOICES, ("custom", "Custom")],
                                   default="space_manager", max_length=32),
        ),
        migrations.AlterField(
            model_name="makerspacerole", name="legacy_role",
            field=models.CharField(blank=True, choices=ROLE_CHOICES, max_length=32, null=True),
        ),
        migrations.CreateModel(
            name="MembershipAdditionalRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                          serialize=False, verbose_name="ID")),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                  to=settings.AUTH_USER_MODEL)),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="additional_roles", to="makerspaces.makerspacemembership")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="additional_memberships", to="makerspaces.makerspacerole")),
            ],
            options={"constraints": [models.UniqueConstraint(
                fields=("membership", "role"), name="membershipadditionalrole_uniq",
            )]},
        ),
    ]
