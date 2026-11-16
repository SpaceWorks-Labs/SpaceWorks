# Final audit 0.12.0 (m22, decision 229(e)): a renewal fully covered by volunteer credit is marked on the
# term instead of recording a 0.01 debt. Additive.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("makerspaces", "0139_guest_pass_immutability"),
    ]

    operations = [
        migrations.AddField(
            model_name="membershipterm",
            name="renewal_covered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
