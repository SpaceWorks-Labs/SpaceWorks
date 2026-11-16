from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0014_public_terms_and_watch")]
    operations = [migrations.AddIndex(model_name="inventorywatch", index=models.Index(
        fields=["makerspace", "ready_at"], condition=models.Q(notified_at__isnull=True),
        name="inv_watch_pending_idx"))]
