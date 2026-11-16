# Hand-written for owner decision 219(h): removed card-design overrides are archived.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('card_designs', '0003_member_card_template_designs'),
    ]

    operations = [
        migrations.AddField(
            model_name='carddesign',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
