# Hand-written for the release-2 ID-card gap lane: the holder's "your card" email format.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('makerspaces', '0127_help_centre_default_on'),
    ]

    operations = [
        migrations.AddField(
            model_name='membercard',
            name='email_format',
            field=models.CharField(choices=[('pdf', 'PDF'), ('png', 'PNG')], default='pdf', max_length=3),
        ),
    ]
