from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0088_setup_event_audience")]
    operations = [migrations.AlterField(
        model_name="makerspace", name="event_default_registration_audience",
        field=models.CharField(max_length=32, default="members", choices=[
            ("members", "Members"), ("accounts", "Authenticated accounts"),
            ("invite", "Invited accounts"), ("participating_organizations", "Participating organizations"),
        ]),
    )]
