# Hand-written for owner decision 219(h): used ID programmes are archived, not deleted.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('id_programmes', '0002_card_email_format'),
    ]

    operations = [
        migrations.AddField(
            model_name='idprogramme',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
