# Decision 220(d)2: a member reports a problem from their own machine session.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('machines', '0032_l23_machine_sessions'),
        ('maintenance', '0007_issue_report_return_line'),
    ]

    operations = [
        migrations.AlterField(
            model_name='issuereport',
            name='source',
            field=models.CharField(choices=[('loan', 'Loan'), ('booking', 'Booking'), ('machine_job', 'Machine job'),
                                            ('session', 'Machine session'), ('staff', 'Staff')], max_length=12),
        ),
        migrations.AddField(
            model_name='issuereport',
            name='machine_session',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='issue_reports', to='machines.machinesession'),
        ),
    ]
