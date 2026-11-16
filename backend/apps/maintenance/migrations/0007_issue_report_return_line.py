# Item 5: a damaged return line handed off to repairs links its one issue report.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hardware_requests', '0030_l12_loans_depth'),
        ('maintenance', '0006_gap_subject_log_cost'),
    ]

    operations = [
        migrations.AddField(
            model_name='issuereport',
            name='return_line',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                       related_name='repair_issue', to='hardware_requests.requesteraccountability'),
        ),
    ]
