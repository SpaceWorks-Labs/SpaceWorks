"""Decision 221(d): the append-only ledger of a plan's included booking hours per term."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0026_booking_replaces"),
        ("makerspaces", "0135_membership_plan_included_hours"),
    ]
    operations = [
        migrations.CreateModel(
            name="IncludedHoursUsage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("booking", "Room booking hours"), ("machine", "Machine time hours")],
                                          max_length=8)),
                ("entry", models.CharField(choices=[("consume", "Consumed"), ("reverse", "Reversed")], max_length=8)),
                ("minutes", models.PositiveIntegerField()),
                ("generation", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="included_hours", to="bookings.booking")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="+", to="makerspaces.makerspace")),
                ("reverses", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                               related_name="+", to="bookings.includedhoursusage")),
                ("term", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name="+", to="makerspaces.membershipterm")),
            ],
            options={
                "ordering": ["created_at", "pk"],
                "indexes": [models.Index(fields=["term", "kind"], name="incl_hours_term_kind_idx")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(minutes__gt=0), name="incl_hours_minutes_positive"),
                    models.CheckConstraint(
                        condition=models.Q(entry="consume", reverses__isnull=True)
                        | models.Q(entry="reverse", reverses__isnull=False),
                        name="incl_hours_reverse_points_back",
                    ),
                    models.UniqueConstraint(condition=models.Q(entry="consume"),
                                            fields=("makerspace", "booking", "generation"),
                                            name="incl_hours_one_consume_per_generation"),
                    models.UniqueConstraint(condition=models.Q(entry="reverse"), fields=("makerspace", "reverses"),
                                            name="incl_hours_one_reversal"),
                ],
            },
        ),
    ]
