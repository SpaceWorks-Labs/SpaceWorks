"""Decision 530: legacy classification is lazy; no mail history is rewritten."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0055_platform_legal_pages"),
        ("payments", "0021_payment_documents"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(
        name="DocumentEmailIntent",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("intent_key", models.CharField(max_length=200)),
            ("state", models.CharField(max_length=32, default="unknown_legacy", choices=[(v, v) for v in (
                "initial_pending", "sent", "skipped_disabled", "skipped_permanent", "recovery_approved", "unknown_legacy",
            )])),
            ("generation", models.PositiveIntegerField(default=0)),
            ("reason", models.CharField(max_length=255, blank=True)),
            ("owner_kind", models.CharField(max_length=16, blank=True)),
            ("owner_id", models.PositiveBigIntegerField(null=True)),
            ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="makerspaces.makerspace")),
            ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="payments.paymentdocument")),
            ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ("email_log", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="integrations.emaillog")),
        ],
        options={"constraints": [models.UniqueConstraint(
            fields=("makerspace", "document", "recipient", "intent_key"), name="unique_document_email_intent",
        )]},
    )]
