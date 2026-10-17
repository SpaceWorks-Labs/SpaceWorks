from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0036_merge_account_split")]
    operations = [
        migrations.AddField(model_name="passwordresetenvelope", name="context", field=models.CharField(default="member", max_length=8, choices=[("member", "Member"), ("staff", "Staff"), ("platform", "Platform")])),
        migrations.AddField(model_name="passwordresetenvelope", name="makerspace", field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, to="makerspaces.makerspace")),
        migrations.AddField(model_name="passwordresetenvelope", name="request_origin", field=models.CharField(max_length=512, blank=True)),
        migrations.AddField(model_name="passwordresetenvelope", name="credential_generation", field=models.PositiveBigIntegerField(default=0)),
    ]
