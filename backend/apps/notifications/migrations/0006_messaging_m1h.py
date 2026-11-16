from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0005_analytics_m1f1")]
    operations = [migrations.AlterField(
        model_name="membernotificationpreference", name="channel",
        field=models.CharField(max_length=16, choices=[("email", "email"), ("in_app", "in_app"),
            ("native_push", "native_push"), ("sms", "sms"), ("whatsapp", "whatsapp")]),
    )]
