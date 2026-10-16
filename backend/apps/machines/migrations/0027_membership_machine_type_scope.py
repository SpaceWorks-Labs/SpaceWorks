import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("machines", "0026_public_detail_materials_intake"),
        ("makerspaces", "0088_fixed_roles_schema"),
    ]

    operations = [
        migrations.CreateModel(
            name="MembershipMachineTypeScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                          serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="machine_type_scopes", to="makerspaces.makerspacemembership")),
                ("machine_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="membership_scopes", to="machines.machinetype")),
            ],
            options={"constraints": [models.UniqueConstraint(
                fields=("membership", "machine_type"), name="membershipmachinetypescope_uniq",
            )]},
        ),
    ]
