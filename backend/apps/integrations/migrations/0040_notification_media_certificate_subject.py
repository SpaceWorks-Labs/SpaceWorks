from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Typed certificate subject and delivery binding for provider media grants.

    Existing rows are payment-document grants, so they already satisfy the
    exactly-one-subject constraint.
    """

    dependencies = [
        ("integrations", "0039_bd_r2_notification_media"),
        ("events", "0017_event_feedback_certificates"),
        ("makerspaces", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationmediagrant",
            name="document",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to="payments.paymentdocument"),
        ),
        migrations.AddField(
            model_name="notificationmediagrant",
            name="certificate",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to="events.eventattendancecertificate"),
        ),
        migrations.AddField(
            model_name="notificationmediagrant",
            name="storage_makerspace",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name="+", to="makerspaces.makerspace"),
        ),
        migrations.AddField(
            model_name="notificationmediagrant",
            name="source_revision",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="notificationmediagrant",
            name="recipient_id_snapshot",
            field=models.PositiveBigIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="notificationmediagrant",
            name="integration_generation",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="notificationmediagrant",
            name="integration_identity",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddConstraint(
            model_name="notificationmediagrant",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(document__isnull=False, certificate__isnull=True)
                    | models.Q(document__isnull=True, certificate__isnull=False)
                ),
                name="notification_media_exact_subject",
            ),
        ),
    ]
