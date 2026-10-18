"""CONVERT checkpoint; refuses populated installations without a drained barrier."""
from django.db import migrations
from ._notification_conversion_v1 import copy


class Migration(migrations.Migration):
    atomic = False
    dependencies = [("integrations", "0041_notification_cutover_expansion")]
    operations = [migrations.RunPython(copy)]
