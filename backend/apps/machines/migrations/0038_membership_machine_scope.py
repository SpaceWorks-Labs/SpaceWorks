import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("machines", "0037_money_three_decimals"),
        ("makerspaces", "0091_fixed_roles_schema"),
    ]

    operations = [
        migrations.CreateModel(
            name="MembershipMachineScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                          serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="machine_scopes", to="makerspaces.makerspacemembership")),
                ("machine", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="membership_scopes", to="machines.machine")),
            ],
            options={"constraints": [models.UniqueConstraint(
                fields=("membership", "machine"), name="membershipmachinescope_uniq",
            )]},
        ),
    ]
