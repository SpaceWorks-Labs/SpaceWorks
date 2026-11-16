# Pairwise judging rows (lane L7), chained off the real events leaf 0058 at build time (2026-10-29).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0058_merge_programme_guards_reimbursements'),
        ('makerspaces', '0109_makerspace_security_lock'),
    ]

    operations = [
        migrations.CreateModel(
            name='JudgePairwiseComparison',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=1)),
                ('outcome', models.CharField(choices=[('previous', 'previous'), ('current', 'current'), ('skip', 'skip')], max_length=8)),
                ('notes', models.TextField(blank=True, max_length=2000)),
                ('submitted_at', models.DateTimeField()),
                ('sequence', models.PositiveIntegerField()),
            ],
            options={
                'ordering': ('round', 'sequence'),
            },
        ),
        migrations.CreateModel(
            name='JudgePairwiseCursor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=1)),
                ('draw_count', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='JudgePairwiseInvalidation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.RemoveConstraint(
            model_name='judginground',
            name='ev_round_mode',
        ),
        migrations.AlterField(
            model_name='judginground',
            name='mode',
            field=models.CharField(choices=[('weighted_1_5', 'Weighted 1–5'), ('top3', 'Top three'), ('pairwise', 'Pairwise comparison')], max_length=16),
        ),
        migrations.AddConstraint(
            model_name='judginground',
            constraint=models.CheckConstraint(condition=models.Q(('mode__in', ('weighted_1_5', 'top3', 'pairwise'))), name='ev_round_mode'),
        ),
        migrations.AddField(
            model_name='judgepairwisecomparison',
            name='current',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='events.judgeassignment'),
        ),
        migrations.AddField(
            model_name='judgepairwisecomparison',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='events.event'),
        ),
        migrations.AddField(
            model_name='judgepairwisecomparison',
            name='judge',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='events.eventroleassignment'),
        ),
        migrations.AddField(
            model_name='judgepairwisecomparison',
            name='makerspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='makerspaces.makerspace'),
        ),
        migrations.AddField(
            model_name='judgepairwisecomparison',
            name='previous',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='events.judgeassignment'),
        ),
        migrations.AddField(
            model_name='judgepairwisecomparison',
            name='round',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pairwise_comparisons', to='events.judginground'),
        ),
        migrations.AddField(
            model_name='judgepairwisecursor',
            name='current',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='events.judgeassignment'),
        ),
        migrations.AddField(
            model_name='judgepairwisecursor',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='events.event'),
        ),
        migrations.AddField(
            model_name='judgepairwisecursor',
            name='judge',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='events.eventroleassignment'),
        ),
        migrations.AddField(
            model_name='judgepairwisecursor',
            name='previous',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='events.judgeassignment'),
        ),
        migrations.AddField(
            model_name='judgepairwisecursor',
            name='round',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pairwise_cursors', to='events.judginground'),
        ),
        migrations.AddField(
            model_name='judgepairwiseinvalidation',
            name='comparison',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='invalidation', to='events.judgepairwisecomparison'),
        ),
        migrations.AddField(
            model_name='judgepairwiseinvalidation',
            name='reason',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='events.judgingreason'),
        ),
        migrations.AddConstraint(
            model_name='judgepairwisecomparison',
            constraint=models.UniqueConstraint(fields=('round', 'sequence'), name='ev_pairwise_sequence'),
        ),
        migrations.AddConstraint(
            model_name='judgepairwisecomparison',
            constraint=models.UniqueConstraint(fields=('round', 'judge', 'previous', 'current'), name='ev_pairwise_pair_once'),
        ),
        migrations.AddConstraint(
            model_name='judgepairwisecomparison',
            constraint=models.CheckConstraint(condition=models.Q(('previous', models.F('current')), _negated=True), name='ev_pairwise_distinct'),
        ),
        migrations.AddConstraint(
            model_name='judgepairwisecomparison',
            constraint=models.CheckConstraint(condition=models.Q(('outcome__in', ('previous', 'current', 'skip'))), name='ev_pairwise_outcome'),
        ),
        migrations.AddConstraint(
            model_name='judgepairwisecursor',
            constraint=models.UniqueConstraint(fields=('round', 'judge'), name='ev_pairwise_cursor_once'),
        ),
    ]
