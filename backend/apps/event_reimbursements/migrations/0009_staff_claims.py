"""Parity C17: a request may be a staff claim (`kind="staff"`), filed by staff for themselves or someone else.

Choices only: no column, constraint or data changes, so the guards and the tenant catalogue are untouched.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_reimbursements', '0008_hackmoney_crew_pool'),
    ]

    operations = [
        migrations.AlterField(
            model_name='grantrequest',
            name='kind',
            field=models.CharField(choices=[('participant', 'participant'), ('crew', 'crew'), ('staff', 'staff')], default='participant', max_length=12),
        ),
    ]
