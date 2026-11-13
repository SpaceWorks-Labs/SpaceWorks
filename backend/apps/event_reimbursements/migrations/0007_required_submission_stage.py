"""G11 (#180): ``required_submission`` says which submission earns travel money.

The old yes/no ``require_project_submission`` stays as its mirror; every programme that required a
submission becomes ``any_stage``, which is exactly what "yes" meant before submission stages.
"""

from django.conf import settings
from django.db import migrations, models


def any_stage_for_yes(apps, schema_editor):
    Programme = apps.get_model("event_reimbursements", "ReimbursementProgramme")
    Programme.objects.filter(require_project_submission=True).update(required_submission="any_stage")


class Migration(migrations.Migration):

    dependencies = [
        ('event_reimbursements', '0006_l21a_stage_and_crew_claims'),
        ('events', '0073_submission_stages_backfill'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='reimbursementprogramme',
            name='required_submission',
            field=models.CharField(choices=[('none', 'none'), ('any_stage', 'any_stage'), ('stage', 'stage'), ('final_stage', 'final_stage'), ('shortlisted_at', 'shortlisted_at'), ('finalist', 'finalist')], default='none', max_length=16),
        ),
        migrations.AddField(
            model_name='reimbursementprogramme',
            name='required_submission_stage',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='reimbursementprogramme',
            constraint=models.CheckConstraint(condition=models.Q(('required_submission__in', ('none', 'any_stage', 'stage', 'final_stage', 'shortlisted_at', 'finalist'))), name='reimb_required_submission'),
        ),
        migrations.AddConstraint(
            model_name='reimbursementprogramme',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('required_submission__in', ('stage', 'shortlisted_at')), _negated=True), models.Q(('required_submission_stage__gte', 1), ('required_submission_stage__lte', 10)), _connector='OR'), name='reimb_required_submission_stage'),
        ),
        migrations.RunPython(any_stage_for_yes, migrations.RunPython.noop),
    ]
