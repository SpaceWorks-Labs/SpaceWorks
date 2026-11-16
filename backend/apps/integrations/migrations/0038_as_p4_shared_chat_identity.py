from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0037_presence_notification_feature")]
    operations = [
        migrations.RemoveConstraint("notificationendpoint", "uniq_live_provider_identity"),
        migrations.AddConstraint("notificationendpoint", models.UniqueConstraint(
            fields=("configuration", "identity_digest", "user"),
            condition=models.Q(revoked_at__isnull=True), name="uniq_live_provider_identity")),
    ]
