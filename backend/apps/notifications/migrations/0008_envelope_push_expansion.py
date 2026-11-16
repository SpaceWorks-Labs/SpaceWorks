"""EXPAND before the shared cutover barrier; no existing push authority is changed."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0007_merge_mobile_preferences"),
        ("integrations", "0041_notification_cutover_expansion"),
        ("accounts", "0041_reconcile_native_account_context"),
    ]
    operations = [
        migrations.AddField(model_name="memberpushdelivery", name="envelope_delivery",
            field=models.ForeignKey(to="integrations.notificationdelivery", null=True,
                related_name="push_children", on_delete=django.db.models.deletion.CASCADE)),
        migrations.AlterField(model_name="memberpushdelivery", name="inbox_row",
            field=models.ForeignKey(to="notifications.notificationinboxrow", null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL)),
        migrations.AddField(model_name="memberpushdelivery", name="retryable",
            field=models.BooleanField(default=False)),
        migrations.AlterField(model_name="memberpushdelivery", name="status",
            field=models.CharField(max_length=8, default="pending", choices=[
                ("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent"),
                ("failed", "Failed"), ("skipped", "Skipped"), ("held", "Held"), ("canceled", "Canceled")
            ])),
    ]
