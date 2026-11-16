from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0036_account_deletion")]

    operations = [
        migrations.AddField(
            model_name="user", name="account_purged_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user", name="deletion_email_ciphertext",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user", name="deletion_username",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.CreateModel(
            name="AccountPurgeProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("done_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="makerspaces.makerspace")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("user", "makerspace"), name="uniq_account_purge_tenant")]},
        ),
        migrations.CreateModel(
            name="AccountPurgeObject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bucket", models.CharField(max_length=255)),
                ("object_key", models.CharField(max_length=500)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("quota_released_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, default="", max_length=128)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="makerspaces.makerspace")),
            ],
            options={"constraints": [models.UniqueConstraint(
                fields=("user", "makerspace", "bucket", "object_key"), name="uniq_account_purge_object",
            )]},
        ),
        migrations.CreateModel(
            name="AppleRefreshCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_id", models.CharField(max_length=255)),
                ("token_ciphertext", models.TextField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("social_identity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.socialidentity")),
            ],
            options={"constraints": [models.UniqueConstraint(
                fields=("social_identity", "client_id"), name="uniq_apple_refresh_client",
            )]},
        ),
        migrations.CreateModel(
            name="AppleRevocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_id", models.CharField(blank=True, max_length=255)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, default="", max_length=128)),
                ("done_at", models.DateTimeField(blank=True, null=True)),
                ("next_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("user", "client_id"), name="uniq_apple_revocation_client")]},
        ),
    ]
