import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    """Parity E-B5: series allowlist entries, a registration pay window, check-in list order and scan undo."""

    dependencies = [
        ('events', '0093_crew_kind_position_teams'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventinvite',
            name='event',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='invites', to='events.event'),
        ),
        migrations.AddField(
            model_name='eventinvite',
            name='series',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='invites', to='events.eventseries'),
        ),
        migrations.AddConstraint(
            model_name='eventinvite',
            constraint=models.UniqueConstraint(fields=('series', 'code_digest'),
                                               name='event_invite_series_unique_code'),
        ),
        migrations.AddConstraint(
            model_name='eventinvite',
            constraint=models.CheckConstraint(
                condition=(Q(event__isnull=False, series__isnull=True)
                           | Q(event__isnull=True, series__isnull=False)),
                name='event_invite_one_target'),
        ),
        migrations.AddField(
            model_name='eventregistration',
            name='pay_by',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='eventcheckinlist',
            name='position',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name='eventcheckinlist',
            options={'ordering': ['event_id', 'position', 'pk']},
        ),
        migrations.AddField(
            model_name='eventcheckinlistscan',
            name='undone_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='eventcheckinlistscan',
            name='undone_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='+', to=settings.AUTH_USER_MODEL),
        ),
    ]
