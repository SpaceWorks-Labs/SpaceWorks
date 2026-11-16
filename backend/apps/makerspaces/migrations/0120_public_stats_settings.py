"""Settings › Public stats (release 2 L26, #170): section order, period, headline and TV mode.

Every default keeps today's page: machines, printing and lending in that order, events and
community off until the Space Manager turns them on, no headline row and TV mode off.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('makerspaces', '0119_retire_staff_mfa_feature'),
    ]

    operations = [
        migrations.AddField(
            model_name='makerspace',
            name='public_stats_sections',
            field=models.CharField(blank=True, default='machines,printing,lending', max_length=120),
        ),
        migrations.AddField(
            model_name='makerspace',
            name='public_stats_period',
            field=models.CharField(
                choices=[('month', 'This month'), ('year', 'This year'), ('all', 'All time'),
                         ('fy', 'This financial year')],
                default='month', max_length=8),
        ),
        migrations.AddField(
            model_name='makerspace',
            name='public_stats_headline',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='makerspace',
            name='public_stats_tv_mode_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='makerspace',
            name='public_stats_tv_refresh_seconds',
            field=models.PositiveSmallIntegerField(default=60),
        ),
    ]
