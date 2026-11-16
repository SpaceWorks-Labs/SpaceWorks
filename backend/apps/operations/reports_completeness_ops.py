"""Decision 248 / 224(a): incidents register, machine jobs register and certification holders.

Each is per space and narrowed to what the viewer manages: incidents through the incident reader scope
(`maintenance.incidents.scope`), machine jobs and certification holders through the machine type scope of the
viewer's role. The incident register and the holder list name people, so they are identity-bearing (a superadmin
needs an open PII window); area managers read their own area's named rows through the report's own area action,
never through `view_audit` (decision 242(h)).
"""

from django.core.exceptions import PermissionDenied

from apps.machines import role_scope
from apps.operations.report_types import ReportResult
from apps.operations.reports_machine_common import requests, spaces
from apps.makerspaces.models import Makerspace

INCIDENT_FIELDS = ("incident_id", "occurred_at", "kind", "severity", "status", "area", "title", "location",
                   "involved", "closed_at")
JOB_FIELDS = ("job_id", "machine_type", "machine", "status", "submitted_at", "completed_at", "estimated_minutes",
              "actual_minutes")
HOLDER_FIELDS = ("machine_type", "certification", "holder", "email", "granted_at", "expires_at", "state")


def _cap(rows, limit):
    return rows if limit is None else rows[:limit]


def _name(user):
    return (user.display_name or user.get_full_name() or user.username) if user else ""


def build_incidents_register(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.maintenance.incidents import scope
    from apps.operations.reports_common import apply_range
    if actor is None:
        raise PermissionDenied()
    space = Makerspace.objects.get(pk=makerspace_id)
    scope.require_incidents(space)
    rows = []
    queryset = apply_range(scope.readable_incidents(actor, space), "occurred_at", date_range)
    for incident in queryset.select_related("involved_user").order_by("-occurred_at", "-pk"):
        rows.append({"incident_id": incident.pk, "occurred_at": incident.occurred_at, "kind": incident.kind,
                     "severity": incident.severity, "status": incident.status, "area": incident.area,
                     "title": incident.title, "location": incident.location,
                     "involved": _name(incident.involved_user),
                     "closed_at": incident.closed_at})
    return ReportResult(INCIDENT_FIELDS, _cap(rows, limit), {
        "definition": "Incidents and near-misses the viewer may read, newest first. Descriptions and "
                      "resolution notes are not exported."})


def build_machine_jobs(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.operations.reports_common import apply_range
    rows = []
    for space, scope in spaces(makerspace_id, ("machines", "machine_service"), actor):
        queryset = apply_range(requests(space, scope), "created_at", date_range)
        for job in queryset.select_related("assigned_machine", "queue__machine_type").order_by("-created_at", "-pk"):
            rows.append({"job_id": job.pk, "machine_type": job.queue.machine_type.name if job.queue_id else "",
                         "machine": job.assigned_machine.name if job.assigned_machine_id else "",
                         "status": job.status, "submitted_at": job.created_at, "completed_at": job.completed_at,
                         "estimated_minutes": job.estimated_minutes, "actual_minutes": job.actual_minutes})
    return ReportResult(JOB_FIELDS, _cap(rows, limit), {
        "definition": "Machine service jobs in the viewer's machine types, newest first. No requester is named."})


def build_certification_holders(makerspace_id, *, limit=None, date_range=None, actor=None):
    from django.utils import timezone
    from apps.machines.models import CertificationGrant
    now, rows = timezone.now(), []
    for space, scope in spaces(makerspace_id, ("machines",), actor, identities=False):
        grants = CertificationGrant.objects.filter(
            certification_type__makerspace_id=space.pk, revoked_at__isnull=True,
        ).select_related("certification_type__machine_type", "membership__user").order_by(
            "certification_type__machine_type__name", "certification_type__name", "membership__user__username")
        for grant in grants:
            machine_type = grant.certification_type.machine_type
            if not role_scope.scope_covers_type(scope, machine_type):
                continue
            expired = grant.expires_at is not None and grant.expires_at <= now
            user = grant.membership.user
            rows.append({"machine_type": machine_type.name, "certification": grant.certification_type.name,
                         "holder": _name(user), "email": user.email, "granted_at": grant.granted_at,
                         "expires_at": grant.expires_at, "state": "expired" if expired else "valid"})
    return ReportResult(HOLDER_FIELDS, _cap(rows, limit), {
        "definition": "Members holding an unrevoked certification in the viewer's machine types."})
