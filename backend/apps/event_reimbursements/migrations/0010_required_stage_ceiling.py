"""Decision 296 addendum [auto, 243]: submission stages go up to 50, so the grant's required stage can too."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("event_reimbursements", "0009_staff_claims")]

    operations = [
        migrations.RemoveConstraint(model_name="reimbursementprogramme", name="reimb_required_submission_stage"),
        migrations.AddConstraint(
            model_name="reimbursementprogramme",
            constraint=models.CheckConstraint(
                condition=models.Q(models.Q(("required_submission__in", ("stage", "shortlisted_at")), _negated=True),
                                   models.Q(("required_submission_stage__gte", 1), ("required_submission_stage__lte", 50)),
                                   _connector="OR"),
                name="reimb_required_submission_stage"),
        ),
    ]
