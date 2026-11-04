"""Problem reports disclose only navigation summaries to hardware staff."""
from apps.accounts import rbac
from apps.integrations.email_templates_registry_helpers import bag
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.hardware_requests.notifications_p2 import safe_adapter
from .models import PublicProblemReport
from .notifications_p2 import fanout, revision

KIND = "hardware.problem_report"


def eligible(envelope):
    row = rbac.scope_notification_policy(PublicProblemReport.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(pk=envelope.source_id).first()
    return bool(row and envelope.audience == "staff" and row.resolved_at is None
                and revision(row.created_at, row.request_id, row.requester_id) == envelope.revision)


@safe_adapter
def notify_report(row):
    return fanout(space=row.makerspace, feature="hardware_requests", stream="hardware",
        event="problem_report.filed", kind=KIND, source=row.pk, subject=row,
        version=revision(row.created_at, row.request_id, row.requester_id),
        staff={"subject": "Tool problem reported",
               "text": f"Problem report #{row.pk} filed for loan #{row.loan_id}. Review in the staff console."},
        context={"problem_report_id": row.pk},
        staff_context={"makerspace": bag(name=row.makerspace.name), "problem_report_id": row.pk})


def register():
    register_source(KIND, NotificationSource(eligible))
