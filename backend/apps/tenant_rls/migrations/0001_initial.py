"""Policy functions and the L25 fixed-role map. Per-table policies are generated after
every ``migrate`` by ``tenant_rls.sync`` (post_migrate), never written here by hand."""

from django.db import migrations, models
import django.db.models.deletion

from apps.tenant_rls.sql import DROP_FUNCTIONS, FUNCTIONS


class Migration(migrations.Migration):
    initial = True

    dependencies = [("makerspaces", "0118_security_policy")]

    operations = [
        migrations.CreateModel(
            name="FixedRoleScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role_name", models.CharField(max_length=63, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("makerspace", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="+", to="makerspaces.makerspace")),
            ],
        ),
        migrations.RunSQL(list(FUNCTIONS), list(reversed(DROP_FUNCTIONS))),
    ]
