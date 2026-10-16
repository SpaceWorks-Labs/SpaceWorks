from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0027_oidcbrowserattempt_surface")]

    operations = [migrations.CreateModel(
        name="ReauthenticationSession",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("session_id", models.CharField(max_length=128, unique=True)),
            ("surface", models.CharField(max_length=16)),
            ("auth_generation", models.CharField(max_length=64)),
            ("credential_fingerprint", models.CharField(max_length=64)),
            ("mfa_version", models.CharField(blank=True, max_length=36)),
            ("auth_time", models.DateTimeField(null=True)),
            ("social_verified_at", models.DateTimeField(null=True)),
            ("enrollment_confirmed_at", models.DateTimeField(null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ],
    )]
