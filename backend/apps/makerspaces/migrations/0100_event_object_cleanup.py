from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0099_page_object_cleanup")]
    operations = [
        migrations.AlterField(model_name="publicpageobjectcleanup", name="owner_kind",
            field=models.CharField(max_length=16, choices=[("makerspace", "Makerspace"),
                ("organization", "Organization"), ("event", "Event website")])),
        migrations.AddField(model_name="publicpageobjectcleanup", name="storage_accounted",
            field=models.BooleanField(default=True)),
        migrations.AddField(model_name="publicpageobjectcleanup", name="ownership_proven",
            field=models.BooleanField(default=False)),
        migrations.AddIndex(model_name="publicpageobjectcleanup", index=models.Index(
            fields=["owner_kind", "owner_id", "storage_accounted", "completed_at"], name="page_cleanup_owner_debt")),
    ]
