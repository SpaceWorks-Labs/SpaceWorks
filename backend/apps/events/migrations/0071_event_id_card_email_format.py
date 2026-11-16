# Hand-written for the release-2 ID-card gap lane: the holder's "your card" email format.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0070_mentor_drop_in'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventidcard',
            name='email_format',
            field=models.CharField(choices=[('pdf', 'PDF'), ('png', 'PNG')], default='pdf', max_length=3),
        ),
    ]
