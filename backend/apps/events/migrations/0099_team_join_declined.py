from django.db import migrations, models


class Migration(migrations.Migration):
    """Decision 301: a team leader can decline a join request (state `declined`, audited, requester told)."""

    dependencies = [
        ("events", "0098_event_card_roles_badge_prints"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hackathonteammember",
            name="state",
            field=models.CharField(
                choices=[("invited", "invited"), ("requested", "requested"), ("active", "active"),
                         ("left", "left"), ("removed", "removed"), ("declined", "declined")],
                default="requested", max_length=12),
        ),
    ]
