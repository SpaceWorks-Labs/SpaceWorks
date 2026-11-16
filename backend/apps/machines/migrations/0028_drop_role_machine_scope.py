from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0092_fixed_roles_data"),
        ("machines", "0027_membership_machine_type_scope"),
    ]

    operations = [
        migrations.DeleteModel(name="RoleMachineScope"),
        migrations.DeleteModel(name="RoleMachineTypeScope"),
    ]
