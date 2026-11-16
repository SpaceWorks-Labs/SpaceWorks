"""The holder's choice to show their name on public certificate verification (default off)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0083_certificate_signatories'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventattendancecertificate',
            name='holder_name_public',
            field=models.BooleanField(default=False),
        ),
    ]
