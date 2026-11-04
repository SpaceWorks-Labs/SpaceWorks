# GAP2 M1 (#102): what an item or room maintenance run cost (also a ledger expense).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maintenance', '0005_l16_repairs'),
    ]

    operations = [
        migrations.AddField(
            model_name='subjectmaintenancelog',
            name='cost',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddConstraint(
            model_name='subjectmaintenancelog',
            constraint=models.CheckConstraint(condition=models.Q(('cost__isnull', True), ('cost__gte', 0), _connector='OR'), name='subject_log_cost_nonnegative'),
        ),
    ]
