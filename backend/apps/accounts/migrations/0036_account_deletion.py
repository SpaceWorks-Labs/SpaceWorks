from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0035_mobile_app_identity")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="deletion_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="deletion_purge_after",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="phoneverificationchallenge",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("link", "Link a phone number"),
                    ("login", "Sign in with a phone number"),
                    ("reauth", "Reauthenticate with a phone number"),
                ],
                max_length=16,
            ),
        ),
    ]
