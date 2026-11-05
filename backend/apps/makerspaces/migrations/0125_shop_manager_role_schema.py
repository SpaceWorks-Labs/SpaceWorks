"""Release 2 L22 (#137): the Shop Manager joins the fixed role catalogue.

Renumbered from 0120 after L16's Technician (0121-0122), L3's 0123 and L18's 0124; the vocabulary
and the fixed catalogue keep the Technician. Schema first -- the role vocabulary and the fixed-catalogue constraint -- so the next
migration can seed one Shop Manager row into every existing makerspace.
"""

from django.db import migrations, models

ROLE_CHOICES = [
    ("space_manager", "Space Manager"), ("inventory_manager", "Inventory Manager"),
    ("print_manager", "Print Manager"), ("machine_manager", "Machine Manager"),
    ("event_manager", "Event Manager"), ("booking_manager", "Booking Manager"),
    ("handover", "Handover"), ("technician", "Technician"), ("shop_manager", "Shop Manager"),
]
FIXED = ("space_manager", "inventory_manager", "machine_manager", "event_manager", "booking_manager",
         "handover", "technician", "shop_manager", "member")


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0124_l18_calendar_feed_switches")]

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
