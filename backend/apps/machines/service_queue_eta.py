"""ORM adapter for the pure queue-ETA simulator.

Callers pass rows they have ALREADY authorized (a public token, the member's own
requests, a staff partition, a public machine page). This module never authorizes an
actor; it pins every read to the target's tenant through ``rbac.scope_verified_tenant``
and loads scalar columns only, so other requesters' encrypted names and contact data
are never fetched or decrypted for the arithmetic.

Budget: at most four domain SELECTs per tenant snapshot -- queues, machines (joined
to their buckets), running jobs, waiting jobs -- whatever the number of targets,
scopes or machines. A snapshot is request-scoped: build one per response, never cache
it across requests and never reuse one built before a mutation.
"""

from collections import defaultdict
from types import SimpleNamespace

from django.db.models import Q
from django.utils import timezone

from apps.accounts import rbac
from apps.machines.job_order import order_key
from apps.machines.models import Machine, MachineServiceRequest, ServiceQueue
from apps.machines.service_queue_eta_core import (
    INACTIVE, Forecast, JobRecord, MachineRecord, ScopeRecord, Timeline, UNAVAILABLE, lane_summary, project,
)

WAITING = (MachineServiceRequest.Status.PENDING, MachineServiceRequest.Status.ACCEPTED)
RUNNING = MachineServiceRequest.Status.IN_PROGRESS
LIVE = frozenset((*WAITING, RUNNING))


def _unattended():
    from django.db.models import OuterRef, Subquery

    from apps.machines.models import MakerspaceMachineTypePolicy
    return Subquery(MakerspaceMachineTypePolicy.objects.filter(
        makerspace_id=OuterRef("makerspace_id"), machine_type_id=OuterRef("machine_type_id"),
    ).values("runs_unattended")[:1])


def _runs_unattended(slug, stored):
    from apps.machines.job_policy import UNATTENDED_SLUGS
    return slug in UNATTENDED_SLUGS if stored is None else bool(stored)


def _on_the_calendar(tenant, job, payload):
    """Attended work only happens while the space is open: push start/finish into open hours."""
    from apps.makerspaces.opening_hours import advance_open, has_hours
    group = tenant.timeline.scopes.get(job.scope)
    if (tenant.calendar is None or group is None or group.group[1] not in tenant.attended
            or not has_hours(tenant.calendar) or payload["finish_in_minutes"] is None):
        return payload
    now = payload["calculated_at"]
    started = payload["estimated_start_at"] is not None and payload["estimated_start_at"] < now
    start = payload["estimated_start_at"] if started else advance_open(tenant.calendar, now,
                                                                       payload["start_in_minutes"])
    finish = advance_open(tenant.calendar, now, payload["finish_in_minutes"])
    if start is None or finish is None:
        return {**payload, "estimated_start_at": None, "estimated_finish_at": None, "start_in_minutes": None,
                "finish_in_minutes": None, "confidence": UNAVAILABLE}
    minutes = lambda at: max(0, round((at - now).total_seconds() / 60))  # noqa: E731
    return {**payload, "estimated_start_at": start, "estimated_finish_at": finish,
            "start_in_minutes": minutes(start), "finish_in_minutes": minutes(finish)}


def _now():
    """The one wall-clock read per snapshot (tests pin it here)."""
    return timezone.now()


def _minutes(*values):
    return next((int(value) for value in values if value and value > 0), None)


class _TenantSnapshot:
    def __init__(self, makerspace_id, now, targets, machine_ids):
        self.makerspace_id = makerspace_id
        queues = list(rbac.scope_verified_tenant(ServiceQueue.objects.all(), makerspace_id).values_list(
            "id", "machine_type_id", "is_active", "capacity"))
        # The opening-hours calendar and each type's attended flag ride on this same SELECT
        # (#142 OQ-11), so the four-query budget holds.
        rows = list(rbac.scope_verified_tenant(Machine.objects.all(), makerspace_id).annotate(
            unattended=_unattended()).values_list(
            "id", "machine_type_id", "is_active", "status", "service_buckets__id", "service_buckets__is_active",
            "machine_type__slug", "unattended", "makerspace__opening_hours", "makerspace__timezone"))
        machines = [row[:6] for row in rows]
        self.calendar = SimpleNamespace(opening_hours=rows[0][8], timezone=rows[0][9]) if rows else None
        self.attended = {row[1] for row in rows if not _runs_unattended(row[6], row[7])}
        queue_type = {row[0]: row[1] for row in queues}
        machine_type = {row[0]: row[1] for row in machines}
        bucket_machine = {row[4]: row[0] for row in machines if row[4] is not None}
        types = set()
        for row in targets:
            if row.queue_id in queue_type:
                types.add(queue_type[row.queue_id])
            elif row.bucket_id in bucket_machine:
                types.add(machine_type[bucket_machine[row.bucket_id]])
        types |= {machine_type[mid] for mid in machine_ids if mid in machine_type}
        self.machine_records, self.scope_records, seen = [], [], set()
        for mid, type_id, active, status, bucket_id, bucket_active in machines:
            if type_id not in types:
                continue
            group = (makerspace_id, type_id)
            if mid not in seen:
                seen.add(mid)
                self.machine_records.append(MachineRecord(mid, group, active, status))
            if bucket_id is not None:
                self.scope_records.append(ScopeRecord(("bucket", bucket_id), group, bool(bucket_active), machine_id=mid))
        for qid, type_id, active, capacity in queues:
            if type_id in types:
                self.scope_records.append(ScopeRecord(("queue", qid), (makerspace_id, type_id), active, capacity))
        self.running, self.waiting = [], []
        if types:
            self._load_jobs(types)
        self.jobs = {job.id: job for job in (*self.running, *self.waiting)}
        self.timeline = Timeline(now, self.machine_records, self.scope_records, self.running, self.waiting,
                                 probe_ids=[row.pk for row in targets])

    def _load_jobs(self, types):
        rows = rbac.scope_verified_tenant(MachineServiceRequest.objects.all(), self.makerspace_id)
        typed = Q(queue__machine_type_id__in=types) | Q(bucket__machine__machine_type_id__in=types)
        running = rows.filter(typed | Q(assigned_machine__machine_type_id__in=types), status=RUNNING)
        for pk, qid, bid, mid, started, run_minutes, minutes, created, batch in running.values_list(
                "id", "queue_id", "bucket_id", "assigned_machine_id", "started_at",
                "run_estimated_minutes", "estimated_minutes", "created_at", "batch_id"):
            scope = ("bucket", bid) if bid else ("queue", qid)
            self.running.append(JobRecord(pk, scope, RUNNING, order_key(False, None, created),
                                          _minutes(run_minutes, minutes), started_at=started, machine_id=mid,
                                          batch_id=batch))
        for pk, status, qid, bid, minutes, created, queued, urgent, preassigned in rows.filter(
                typed, status__in=WAITING).values_list(
                "id", "status", "queue_id", "bucket_id", "estimated_minutes", "created_at", "queued_at", "urgent",
                "preassigned_machine_id"):
            scope = ("bucket", bid) if bid else ("queue", qid)
            # `created_at` carries the queue order key (#142 OQ-6): urgent first, then the anchor.
            self.waiting.append(JobRecord(pk, scope, status, order_key(urgent, queued, created), _minutes(minutes),
                                          machine_id=preassigned))


class QueueSnapshot:
    """Read-only, request-scoped ETA/count/summary view over one simulation per tenant."""

    def __init__(self, now, tenants):
        self.now = now
        self._tenants = tenants

    def _locate(self, request_id):
        for tenant in self._tenants.values():
            job = tenant.jobs.get(request_id)
            if job is not None:
                return tenant, job
        return None, None

    def eta(self, row):
        """Nullable ETA for one already-authorized row; terminal rows have none."""
        if row is None or row.status not in LIVE:
            return None
        tenant, job = self._locate(row.pk)
        if job is None:
            return {"calculated_at": self.now, "estimated_start_at": None, "estimated_finish_at": None,
                    "start_in_minutes": None, "finish_in_minutes": None, "confidence": UNAVAILABLE,
                    "reasons": [INACTIVE], "approved_ahead": 0, "awaiting_review_ahead": 0,
                    "active_machine_count": 0, "missing_estimate_count": 0}
        forecast = tenant.timeline.forecasts.get(job.id) or Forecast(reasons={INACTIVE})
        payload = _on_the_calendar(tenant, job, project(self.now, forecast))
        facts = tenant.timeline.facts(job)
        payload.update({key: facts[key] for key in (
            "approved_ahead", "awaiting_review_ahead", "active_machine_count", "missing_estimate_count")})
        return payload

    def counts(self, row):
        """Legacy queue_position/approved/awaiting-review counts for waiting rows."""
        if row is None or row.status not in WAITING:
            return None
        tenant, job = self._locate(row.pk)
        if job is None:
            return None
        facts = tenant.timeline.facts(job)
        return {"position": facts["position"], "approved_ahead": facts["approved_ahead"],
                "awaiting_review_ahead": facts["awaiting_review_ahead"]}

    def machine_summary(self, machine):
        tenant = self._tenants.get(machine.makerspace_id)
        if tenant is None:
            return None
        return lane_summary(self.now, tenant.timeline, machine.pk)


def queue_snapshot_for(requests=(), *, machines=(), now=None):
    """Build one snapshot for authorized request rows and/or machines (≤4 SELECTs per tenant)."""
    now = now or _now()
    targets = defaultdict(list)
    machine_ids = defaultdict(set)
    for row in requests:
        if row.status in LIVE:
            targets[row.makerspace_id].append(row)
    for machine in machines:
        machine_ids[machine.makerspace_id].add(machine.pk)
    tenants = {
        makerspace_id: _TenantSnapshot(makerspace_id, now, targets.get(makerspace_id, []),
                                       machine_ids.get(makerspace_id, set()))
        for makerspace_id in set(targets) | set(machine_ids)
    }
    return QueueSnapshot(now, tenants)


def machine_queue_summaries_for(machines, *, now=None):
    """Per-machine ``{length, eta_minutes, estimated_clear_at, calculated_at, confidence, reasons}``."""
    machines = list(machines)
    snapshot = queue_snapshot_for(machines=machines, now=now)
    return {machine.pk: snapshot.machine_summary(machine) for machine in machines}
