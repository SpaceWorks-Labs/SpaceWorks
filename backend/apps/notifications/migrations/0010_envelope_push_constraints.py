"""Enforce parent/device identity only after every original attempt is accounted for."""
import django.db.models.deletion
from django.db import migrations, models
from ._push_conversion_v1 import verify


class Migration(migrations.Migration):
    dependencies = [("notifications", "0009_envelope_push_conversion")]
    operations = [
        migrations.RunPython(verify),
        migrations.RemoveConstraint(model_name="memberpushdelivery", name="uniq_member_push_delivery"),
        migrations.AlterField(model_name="memberpushdelivery", name="envelope_delivery",
            field=models.ForeignKey(to="integrations.notificationdelivery", related_name="push_children",
                                    on_delete=django.db.models.deletion.CASCADE)),
        migrations.AddConstraint(model_name="memberpushdelivery", constraint=models.UniqueConstraint(
            fields=["envelope_delivery", "push_device"], name="uniq_envelope_push_device")),
    ]
