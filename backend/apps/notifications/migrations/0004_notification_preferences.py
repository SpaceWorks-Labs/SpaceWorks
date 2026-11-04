# Notification contract schema; runtime drift checked by makemigrations --check.
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notifications', '0003_broadcasts_and_digests'),
        ('makerspaces', '0093_fixed_roles_constraint'),
    ]
    operations = [
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('makerspace', models.ForeignKey('makerspaces.Makerspace', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
                ('category', models.CharField(max_length=32)),
                ('channels', models.JSONField(default=list)),
                ('email_fallback', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=['makerspace', 'user', 'category'], name='uniq_personal_channel_selection')],
            },
        ),
    ]
