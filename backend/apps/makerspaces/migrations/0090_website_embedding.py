from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0089_organization_event_audience")]
    operations = [migrations.AddField(model_name="makerspace", name="website_embed_origins", field=models.JSONField(default=list, blank=True))]
