"""Release 2 L22 (#137): the Shop Manager joins the fixed role catalogue.

Schema first -- the role vocabulary and the fixed-catalogue constraint -- so the next
migration can seed one Shop Manager row into every existing makerspace.
"""

from django.db import migrations, models

ROLE_CHOICES = [
    ("space_manager", "Space Manager"), ("inventory_manager", "Inventory Manager"),
    ("print_manager", "Print Manager"), ("machine_manager", "Machine Manager"),
    ("event_manager", "Event Manager"), ("booking_manager", "Booking Manager"),
    ("handover", "Handover"), ("shop_manager", "Shop Manager"),
]
FIXED = ("space_manager", "inventory_manager", "machine_manager", "event_manager", "booking_manager",
         "handover", "shop_manager", "member")


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0119_l3_member_cards")]

    operations = [
        migrations.RemoveConstraint(model_name="makerspacerole", name="makerspacerole_fixed_catalogue"),
        migrations.AlterField(
            model_name="makerspacemembership", name="role",
            field=models.CharField(choices=[*ROLE_CHOICES, ("custom", "Custom")], default="space_manager",
                                   max_length=32),
        ),
        migrations.AlterField(
            model_name="makerspacerole", name="legacy_role",
            field=models.CharField(blank=True, choices=ROLE_CHOICES, max_length=32, null=True),
        ),
        migrations.AddConstraint(
            model_name="makerspacerole",
            constraint=models.CheckConstraint(
                condition=models.Q(is_default=True, is_protected=True, slug__in=FIXED),
                name="makerspacerole_fixed_catalogue",
            ),
        ),
    ]
