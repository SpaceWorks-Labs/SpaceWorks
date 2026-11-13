from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0057_user_preferred_locale'),
    ]

    operations = [
        migrations.AddField(
            model_name='oidcbrowserattempt',
            name='next_path',
            field=models.CharField(blank=True, default='', max_length=512),
        ),
    ]
