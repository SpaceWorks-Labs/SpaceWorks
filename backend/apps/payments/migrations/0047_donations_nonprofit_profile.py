"""Decision 242(m): the non-profit profile and opt-in donor recognition (release 0.12.0).

`DonationSettings` gains the profile (non-profit switch, legal name, registration number, the typed
tax-exemption list, receipt signatory and footer); `Donation` gains the giver's opt-in to be named
among a campaign's supporters (off by default). A space that already issued 80G receipts keeps
doing so: its registration becomes the list's India 80G entry and the space is marked a non-profit.
"""

from django.db import migrations, models


def adopt_80g(apps, schema_editor):
    Settings = apps.get_model("payments", "DonationSettings")
    rows = Settings.objects.using(schema_editor.connection.alias).exclude(tax_exempt_registration_number="")
    for row in rows.iterator():
        row.is_nonprofit = True
        row.tax_exemptions = [{
            "scheme": "in_80g", "number": row.tax_exempt_registration_number,
            "valid_from": row.tax_exempt_valid_from.isoformat() if row.tax_exempt_valid_from else "",
            "valid_until": row.tax_exempt_valid_until.isoformat() if row.tax_exempt_valid_until else ""}]
        row.save(update_fields=["is_nonprofit", "tax_exemptions"])


class Migration(migrations.Migration):
    dependencies = [("payments", "0046_guest_pass_subject")]

    operations = [
        migrations.AddField(model_name="donationsettings", name="is_nonprofit",
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name="donationsettings", name="legal_name",
                            field=models.CharField(blank=True, default="", max_length=200)),
        migrations.AddField(model_name="donationsettings", name="organization_registration_number",
                            field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="donationsettings", name="tax_exemptions",
                            field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="donationsettings", name="signatory_name",
                            field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField(model_name="donationsettings", name="signatory_title",
                            field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField(model_name="donationsettings", name="receipt_footer",
                            field=models.CharField(blank=True, default="", max_length=500)),
        migrations.AddField(model_name="donation", name="recognize_publicly",
                            field=models.BooleanField(default=False)),
        migrations.RunPython(adopt_80g, migrations.RunPython.noop),
    ]
