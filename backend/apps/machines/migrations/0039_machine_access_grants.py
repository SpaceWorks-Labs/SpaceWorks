"""Decision 319: machine access grants and the per-machine open-to-all-members switch."""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("machines", "0038_membership_machine_scope"),
        ("makerspaces", "0091_fixed_roles_schema"),
    ]

    operations = [
        migrations.AddField(model_name="machine", name="open_to_all_members",
                            field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name="MachineAccessGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("granted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.TextField(blank=True)),
                ("source", models.CharField(choices=[("staff", "Granted by staff"),
                                                     ("migration", "Converted from a certification")],
                                            default="staff", max_length=12)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("expiry_notice_sent_at", models.DateTimeField(blank=True, null=True)),
                ("granted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="machine_access_granted", to=settings.AUTH_USER_MODEL)),
                ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                              related_name="access_grants", to="machines.machine")),
                ("machine_type", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                                   related_name="access_grants", to="machines.machinetype")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="machine_access_grants", to="makerspaces.makerspace")),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name="machine_access_grants", to=settings.AUTH_USER_MODEL)),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="machine_access_revoked", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-granted_at", "-pk"],
                "indexes": [models.Index(fields=["makerspace", "member"], name="machaccess_space_member_idx")],
                "constraints": [
                    models.CheckConstraint(condition=(models.Q(machine__isnull=False, machine_type__isnull=True)
                                                      | models.Q(machine__isnull=True, machine_type__isnull=False)),
                                           name="machaccess_machine_xor_type"),
                    # Per makerspace (336k/M8): a built-in type (makerspace NULL) is granted in each space.
                    models.UniqueConstraint(fields=("makerspace", "member", "machine"), name="machaccess_one_live_machine",
                                            condition=models.Q(revoked_at__isnull=True, machine__isnull=False)),
                    models.UniqueConstraint(fields=("makerspace", "member", "machine_type"), name="machaccess_one_live_type",
                                            condition=models.Q(revoked_at__isnull=True, machine_type__isnull=False,
                                                               machine__isnull=True)),
                ],
            },
        ),
    ]
