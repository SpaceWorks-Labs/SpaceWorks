import uuid

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


def bind_existing_work(apps, schema_editor):
    alias = schema_editor.connection.alias
    User = apps.get_model("accounts", "User")
    Progress = apps.get_model("accounts", "AccountPurgeProgress")
    Object = apps.get_model("accounts", "AccountPurgeObject")
    Credential = apps.get_model("accounts", "AppleRefreshCredential")
    Revocation = apps.get_model("accounts", "AppleRevocation")
    started = set(Progress.objects.using(alias).values_list("user_id", flat=True))
    started.update(Object.objects.using(alias).values_list("user_id", flat=True))
    User.objects.using(alias).filter(pk__in=started, deletion_requested_at__isnull=False).update(purge_started_at=timezone.now())
    for row in Revocation.objects.using(alias).all().iterator():
        user = User.objects.using(alias).get(pk=row.user_id)
        row.created_at = user.deletion_requested_at or timezone.now()
        credential = Credential.objects.using(alias).filter(
            social_identity__user_id=row.user_id, client_id=row.client_id,
        ).first()
        if credential:
            row.credential_id = credential.pk
            row.credential_version = credential.version
            if row.done_at is None:
                row.token_ciphertext = credential.token_ciphertext
        row.save(using=alias)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0037_account_purge")]
    operations = [
        migrations.AddField(model_name="user", name="purge_started_at", field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="user", name="account_restored_at", field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="passwordresetenvelope", name="purpose", field=models.CharField(
            max_length=16, default="reset", choices=[("reset", "Reset"), ("restore", "Restore")])),
        migrations.AddField(model_name="phoneverificationchallenge", name="credential_fingerprint",
                            field=models.CharField(max_length=64, blank=True, default="")),
        migrations.AlterField(model_name="phoneverificationchallenge", name="purpose", field=models.CharField(
            max_length=16, choices=[("link", "Link a phone number"), ("login", "Sign in with a phone number"),
                                   ("reauth", "Reauthenticate with a phone number"), ("restore", "Restore an archived account")])),
        migrations.AddField(model_name="applerefreshcredential", name="version", field=models.UUIDField(default=uuid.uuid4)),
        migrations.AddField(model_name="applerevocation", name="token_ciphertext", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="applerevocation", name="credential_id", field=models.PositiveBigIntegerField(null=True, blank=True)),
        migrations.AddField(model_name="applerevocation", name="credential_version", field=models.UUIDField(null=True, blank=True)),
        migrations.AddField(model_name="applerevocation", name="created_at", field=models.DateTimeField(default=timezone.now)),
        migrations.RemoveConstraint(model_name="applerevocation", name="uniq_apple_revocation_client"),
        migrations.RunPython(bind_existing_work, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="applerevocation", constraint=models.UniqueConstraint(
            fields=["user", "client_id", "credential_version"], name="uniq_apple_revocation_version")),
        migrations.CreateModel(name="AccountRestoreIntent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ("token_digest", models.CharField(max_length=64, unique=True)),
            ("credential_fingerprint", models.CharField(max_length=64)),
            ("provider", models.CharField(max_length=100)),
            ("nonce_digest", models.CharField(max_length=64)),
            ("origin", models.CharField(max_length=500)),
            ("redirect_uri", models.URLField(max_length=1000)),
            ("pending_secret", models.TextField(blank=True)),
            ("delivery", models.CharField(max_length=16, default="web")),
            ("client_platform", models.CharField(max_length=16, default="web")),
            ("attestation_challenge", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                                       to="accounts.deviceattestationchallenge")),
            ("expires_at", models.DateTimeField()),
            ("consumed_at", models.DateTimeField(null=True)),
        ]),
    ]
