"""Per-kind certificate designs: a template revision may be one certificate kind's own design."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0081_certificate_organiser_thanks'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventcertificatetemplaterevision',
            name='certificate_kind',
            field=models.CharField(blank=True, default='', max_length=24),
        ),
    ]
