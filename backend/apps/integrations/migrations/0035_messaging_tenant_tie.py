from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0034_messaging_m1h")]

    operations = [
        migrations.AlterField(
            model_name="messagingdelivery",
            name="skip_reason",
            field=models.CharField(blank=True, max_length=64, choices=[
                ("tenant_unservable", "Tenant unavailable"),
                ("module_disabled", "Channel module disabled"),
                ("feature_unavailable", "Source feature unavailable"),
                ("matrix_disabled", "Notification rule disabled"),
                ("account_inactive", "Account inactive or restricted"),
                ("no_membership", "No active local membership"),
                ("no_tenant_tie", "No tie to this makerspace"),
                ("membership_opted_out", "Membership notifications disabled"),
                ("recipient_changed", "Recipient selection or scope changed"),
                ("personal_disabled", "Personal preference disabled"),
                ("phone_unverified", "Phone unverified"),
                ("no_consent", "No live consent"),
                ("sender_unavailable", "Sender unavailable"),
                ("no_template", "No approved audience template"),
                ("quota_exceeded", "Quota exhausted"),
                ("source_changed", "Source removed or scope changed"),
                ("identity_unconfirmed", "Recipient correlation unconfirmed"),
            ]),
        ),
    ]
