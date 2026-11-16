"""Pure machine-service queue simulator: plain records in, projections out.

No queries, writes, wall-clock reads, PII or actor logic live here. The ORM adapter
(`service_queue_eta.py`) loads tenant-scoped scalar records and injects one aware
``now``. Offsets are full-precision minutes from that ``now``; only the boundary
(`project`) rounds them, so timestamps and minute values never drift apart.

The forecast is a type-level timeline: every bucket/queue of one (makerspace, machine
type) shares its machines. Only ACCEPTED rows reserve simulated time, in
``created_at, id`` order (a forecast tie-break, never a dispatch policy). A bucket job
is bound to its one machine; a pooled job takes the earliest-free compatible machine,
tie-broken on machine id. Unknown work never counts as zero: it taints what depends on
it and the affected projections are withheld (``unavailable``).
"""

import math
from dataclasses import dataclass, field
from datetime import timedelta

from apps.machines.service_queue_eta_records import (  # noqa: F401 - re-exported vocabulary
    AWAITING, BLOCKING, CARRIED, COMPETING, ESTIMATED, INACTIVE, MISSING, NO_MACHINE,
    OVERDUE, OVERDUE_FLOOR_MINUTES, REASONS, ROUGH, SOFT, STEP_MINUTES, UNAVAILABLE,
    UNKNOWN_RUN, Forecast, JobRecord, MachineRecord, ScopeRecord, confidence,
    ordered_reasons, project, round_up,
)


@dataclass
class _Lane:
    free: float = 0.0
    known: bool = True
    reasons: set = field(default_factory=set)
    scopes: set = field(default_factory=set)
    length: int = 0


def _elapsed(now, started_at):
    return max(0.0, (now - started_at).total_seconds() / 60)


def _release(now, job):
    """Remaining minutes of a running job, or None with the reason it is unknown."""
    if job.started_at is None:
        return None, {UNKNOWN_RUN}
    if job.minutes is None:
        return None, {MISSING}
    remaining = job.minutes - _elapsed(now, job.started_at)
    if remaining <= 0:
        return float(OVERDUE_FLOOR_MINUTES), {OVERDUE}
    return remaining, set()


class Timeline:
    """One snapshot's simulation; read results through ``forecasts``/``lanes``."""

    def __init__(self, now, machines, scopes, running, waiting, probe_ids=()):
        self.now = now
        self.machines = {row.id: row for row in machines}
        self.scopes = {row.key: row for row in scopes}
        self.running = list(running)
        self.waiting = list(waiting)
        self.forecasts = {}
        self.lanes = {}
        self._slots = {key: [] for key, scope in self.scopes.items() if scope.capacity is not None}
        self._seed()
        wanted = set(probe_ids)
        probes = {job.id for job in self.waiting if job.id in wanted and job.status == "pending"}
        self._ranks = self._rank_scopes()
        for group in sorted({scope.group for scope in self.scopes.values()}, key=repr):
            self._simulate(group, probes)
        for job in self.running:
            self.forecasts[job.id] = self._running_forecast(job)

    def _seed(self):
        per_machine = {}
        for job in self.running:
            if job.machine_id is not None:
                per_machine.setdefault(job.machine_id, []).append(job)
            if job.scope in self._slots:
                remaining, reasons = _release(self.now, job)
                self._slots[job.scope].append((remaining, reasons))
        for machine in self.machines.values():
            if not machine.has_capacity:
                continue
            lane = self.lanes[machine.id] = _Lane()
            jobs = per_machine.get(machine.id, [])
            lane.length = len(jobs)
            batches = {job.batch_id for job in jobs}
            if len(jobs) > 1 and (len(batches) > 1 or None in batches):
                lane.known, lane.reasons = False, {UNKNOWN_RUN}
            elif len(jobs) > 1:
                # One batch run (#142 OQ-9): the machine frees when its longest job ends.
                released = [_release(self.now, job) for job in jobs]
                if any(remaining is None for remaining, _ in released):
                    lane.known, lane.reasons = False, set().union(*(reasons for _, reasons in released))
                else:
                    lane.free = max(remaining for remaining, _ in released)
                    lane.reasons = set().union(*(reasons for _, reasons in released))
            elif jobs:
                # A coherent running row governs availability whatever the machine flag says.
                remaining, reasons = _release(self.now, jobs[0])
                lane.reasons = set(reasons)
                if remaining is None:
                    lane.known = False
                else:
                    lane.free = remaining
            elif machine.status == "running":
                lane.known, lane.reasons = False, {UNKNOWN_RUN}

    def _rank_scopes(self):
        """Prefix counts per scope, computed once: accepted first, then created_at, id."""
        ordered = sorted(self.waiting, key=lambda job: (job.scope, job.status != "accepted", job.created_at, job.id))
        ranks, counters = {}, {}
        for job in ordered:
            accepted, pending, missing = counters.get(job.scope, (0, 0, 0))
            ranks[job.id] = (accepted, pending, missing)
            counters[job.scope] = (accepted + (job.status == "accepted"), pending + (job.status != "accepted"),
                                   missing + (job.status == "accepted" and job.minutes is None))
        self._running_missing = {}
        for job in self.running:
            if job.minutes is None:
                self._running_missing[job.scope] = self._running_missing.get(job.scope, 0) + 1
        return ranks

    def facts(self, job):
        """Scope-local counts that agree with the legacy queue_position fields."""
        scope = self.scopes.get(job.scope)
        machines = len(self._eligible(scope)) if scope is not None and scope.is_active else 0
        if job.status == "in_progress":
            return {"position": None, "approved_ahead": 0, "awaiting_review_ahead": 0,
                    "active_machine_count": machines, "missing_estimate_count": int(job.minutes is None)}
        accepted, pending, missing = self._ranks[job.id]
        own = int(job.minutes is None)
        return {"position": accepted + pending + 1, "approved_ahead": accepted,
                "awaiting_review_ahead": pending if job.status == "pending" else 0,
                "active_machine_count": machines,
                "missing_estimate_count": self._running_missing.get(job.scope, 0) + missing + own}

    def _eligible(self, scope):
        if scope.machine_id is not None:
            return [scope.machine_id] if scope.machine_id in self.lanes else []
        return sorted(mid for mid, row in self.machines.items()
                      if row.group == scope.group and mid in self.lanes)

    def _slot(self, scope):
        """Earliest offset a queue slot frees, honouring ServiceQueue.capacity."""
        if scope.key not in self._slots:
            return 0.0, set(), True
        if scope.capacity == 0:
            return None, {NO_MACHINE}, False
        occupants = sorted(self._slots[scope.key], key=lambda item: math.inf if item[0] is None else item[0])
        if len(occupants) < scope.capacity:
            return 0.0, set(), True
        time, reasons = occupants[len(occupants) - scope.capacity]
        if time is None:
            return None, set(reasons), False
        return time, set(reasons), True

    def _choose(self, job, scope):
        """Return (machine id | None, start | None, reasons). None start means withheld."""
        if not scope.is_active:
            return None, None, {INACTIVE}
        eligible = self._eligible(scope)
        if not eligible:
            return None, None, {NO_MACHINE}
        reasons = set()
        if any(self.lanes[mid].scopes - {scope.key} for mid in eligible):
            reasons.add(COMPETING)
        if job.machine_id in eligible:
            # A job staff pre-assigned to a machine binds to that lane (#141 board).
            eligible = [job.machine_id]
        known = [mid for mid in eligible if self.lanes[mid].known]
        unknown = [mid for mid in eligible if not self.lanes[mid].known]
        best = min(known, key=lambda mid: (self.lanes[mid].free, mid)) if known else None
        floor = min((self.lanes[mid].free for mid in unknown), default=math.inf)
        if best is None or self.lanes[best].free > floor:
            for mid in unknown:
                reasons |= self.lanes[mid].reasons & CARRIED
            return None, None, reasons or {UNKNOWN_RUN}
        slot, slot_reasons, slot_known = self._slot(scope)
        reasons |= slot_reasons
        if not slot_known:
            return None, None, reasons or {UNKNOWN_RUN}
        lane = self.lanes[best]
        reasons |= lane.reasons & CARRIED
        return best, max(lane.free, slot), reasons

    def _simulate(self, group, probes):
        rows = [job for job in self.waiting if job.scope in self.scopes and self.scopes[job.scope].group == group]
        accepted = sorted((job for job in rows if job.status == "accepted"), key=lambda job: (job.created_at, job.id))
        pending = [job for job in rows if job.id in probes]
        due = {}
        for job in pending:
            due.setdefault(self._probe_index(job, accepted), []).append(job)
        for job in due.pop(-1, []):
            self.forecasts[job.id] = self._forecast(job, commit=False)
        for index, job in enumerate(accepted):
            self.forecasts[job.id] = self._forecast(job, commit=True)
            for probe in due.pop(index, []):
                self.forecasts[probe.id] = self._forecast(probe, commit=False)

    @staticmethod
    def _probe_index(job, accepted):
        """A pending job is probed after its own scope's approved work and anything older."""
        index = -1
        for position, row in enumerate(accepted):
            if row.scope == job.scope or (row.created_at, row.id) < (job.created_at, job.id):
                index = position
        return index

    def _forecast(self, job, *, commit):
        scope = self.scopes[job.scope]
        machine_id, start, reasons = self._choose(job, scope)
        if not commit:
            reasons.add(AWAITING)
        if start is None:
            if commit and machine_id is None and scope.is_active:
                self._taint(scope, reasons)
            return Forecast(reasons=reasons)
        if job.minutes is None:
            reasons.add(MISSING)
            if commit:
                lane = self.lanes[machine_id]
                lane.known, lane.free = False, start
                lane.reasons |= {MISSING}
                lane.length += 1
                lane.scopes.add(scope.key)
                self._occupy(scope, None, {MISSING})
            return Forecast(reasons=reasons)
        finish = start + job.minutes
        if commit:
            lane = self.lanes[machine_id]
            lane.free = finish
            lane.reasons = (lane.reasons | reasons) & CARRIED
            lane.length += 1
            lane.scopes.add(scope.key)
            self._occupy(scope, finish, reasons & CARRIED)
        return Forecast(start=start, finish=finish, reasons=reasons)

    def _taint(self, scope, reasons):
        """An approved job whose machine cannot be known makes every candidate unknown."""
        if reasons & {INACTIVE, NO_MACHINE}:
            return
        for mid in self._eligible(scope):
            lane = self.lanes[mid]
            lane.known = False
            lane.reasons |= reasons & CARRIED or {UNKNOWN_RUN}
            lane.scopes.add(scope.key)
        self._occupy(scope, None, reasons & CARRIED)

    def _occupy(self, scope, finish, reasons):
        if scope.key in self._slots:
            self._slots[scope.key].append((finish, set(reasons)))

    def _running_forecast(self, job):
        if job.started_at is None or job.machine_id is None:
            return Forecast(reasons={UNKNOWN_RUN})
        remaining, reasons = _release(self.now, job)
        if remaining is None:
            return Forecast(reasons=reasons)
        return Forecast(start=0.0, finish=remaining, actual_start=job.started_at, reasons=reasons)


def lane_summary(now, timeline, machine_id):
    """Per-machine final free-at summary; unknown or excluded machines never read as zero."""
    machine = timeline.machines.get(machine_id)
    lane = timeline.lanes.get(machine_id)
    base = {"calculated_at": now, "length": 0, "eta_minutes": None, "estimated_clear_at": None}
    if machine is None or lane is None:
        length = sum(1 for job in timeline.running if job.machine_id == machine_id)
        return {**base, "length": length, "confidence": UNAVAILABLE, "reasons": [NO_MACHINE]}
    reasons = set(lane.reasons)
    if not lane.known and not reasons & BLOCKING:
        reasons.add(UNKNOWN_RUN)
    level = confidence(reasons)
    summary = {**base, "length": lane.length, "confidence": level, "reasons": ordered_reasons(reasons)}
    if level != UNAVAILABLE:
        eta = round_up(lane.free)
        summary.update(eta_minutes=eta, estimated_clear_at=now + timedelta(minutes=eta))
    return summary
