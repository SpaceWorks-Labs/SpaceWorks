"""Decision 247/253(e): the stored choice label "Lending" becomes "Inventory loans" (label only, no data change)."""

from django.db import migrations, models

_PRICING = [("loans", "Inventory loans"), ("machines", "Machines"), ("bookings", "Bookings"), ("events", "Events"),
            ("membership", "Membership"), ("shop", "Shop")]
_LEDGER = [("inventory", "Inventory"), ("loans", "Inventory loans"), ("machines", "Machines"),
           ("bookings", "Bookings and rooms"), ("events", "Events"), ("membership", "Membership"),
           ("donations", "Donations and sponsors"), ("shop", "Shop"), ("general", "General")]


class Migration(migrations.Migration):
    dependencies = [("payments", "0047_donations_nonprofit_profile")]

    operations = [
        migrations.AlterField(model_name="pricingdefault", name="domain",
                              field=models.CharField(choices=_PRICING, max_length=16)),
        migrations.AlterField(model_name="priceoverride", name="domain",
                              field=models.CharField(choices=_PRICING, max_length=16)),
        migrations.AlterField(model_name="ledgerentry", name="domain",
                              field=models.CharField(choices=_LEDGER, max_length=16)),
    ]
