"""A prize recovery may name a People's choice payout instead of a judged award (#181 S3 x hack-money G16).

`HackathonPrizeOutcome.award` becomes nullable; every outcome still names an award, except a recovery
(opened, repaid or waived), which may name only the payout of a People's choice winning standing.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0079_peoples_choice_guards'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hackathonprizeoutcome',
            name='award',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='events.eventaward'),
        ),
        migrations.AddConstraint(
            model_name='hackathonprizeoutcome',
            constraint=models.CheckConstraint(condition=models.Q(('award__isnull', False), models.Q(('payout__isnull', False), ('kind__in', ('recovery_opened', 'recovery_repaid', 'recovery_waived'))), _connector='OR'), name='ev_prize_outcome_subject'),
        ),
    ]
