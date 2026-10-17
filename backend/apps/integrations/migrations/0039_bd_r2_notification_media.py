from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0038_as_p4_shared_chat_identity"),
        ("payments", "0021_payment_documents"),
    ]
    operations = [
        migrations.CreateModel(
            name="NotificationMediaGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_digest", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("consumed_at", models.DateTimeField(null=True)),
                ("delivery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                               to="integrations.notificationdelivery")),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                               to="payments.paymentdocument")),
            ],
        ),
    ]
