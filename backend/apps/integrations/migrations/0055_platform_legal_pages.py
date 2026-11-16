"""Parity E-B8: operator-editable privacy / terms pages (a missing row means the shipped default)."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0054_webhook_secret_generated")]

    operations = [
        migrations.CreateModel(
            name="PlatformLegalPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.CharField(choices=[("privacy", "Privacy"), ("terms", "Terms")], max_length=16)),
                ("language", models.CharField(blank=True, default="", max_length=16)),
                ("markdown", models.TextField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("slug", "language")},
        ),
        migrations.AddConstraint(
            model_name="platformlegalpage",
            constraint=models.UniqueConstraint(fields=("slug", "language"), name="uniq_platform_legal_page"),
        ),
    ]
