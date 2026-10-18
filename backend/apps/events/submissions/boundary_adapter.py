"""Concrete B boundary, composed with G source locks and A/C/D/F providers.

No app registry change or grant bypass: G supplies the shared ordered lock
context, then B dispatches each operation to the appropriate domain authority.
"""
from contextlib import contextmanager

from apps.events import event_authority
from .errors import SubmissionError
from .ports import SubmissionContext


class ProgrammeReceipts:
    """Use G's one canonical receipt model; persist stable references only."""
    @staticmethod
    def model():
        from django.apps import apps
        return apps.get_model("events", "EventCommandReceipt")

    def receipt(self, *, event_id, actor_id, operation_id, digest):
        row = self.model().objects.filter(event_id=event_id, actor_id=actor_id,
                                          operation_uuid=operation_id).first()
        if row is None:
            return None
        if row.request_sha256 != digest:
            raise SubmissionError("idempotency_conflict", 409)
        return dict(row.response_reference)

    def store_receipt(self, *, event_id, actor_id, operation_id, digest, result):
        allowed = {"id", "asset_id", "event_id", "version", "generation", "state", "snapshot_id",
                   "triage", "sponsor_consents_revoked", "allowed_actions"}
        self.model().objects.create(event_id=event_id, actor_id=actor_id, operation_uuid=operation_id,
            request_sha256=digest, response_reference={k: v for k, v in result.items() if k in allowed})


class SubmissionBoundaryAdapter(ProgrammeReceipts):
    def __init__(self, *, ordered_context, gate, teams, participants, projects, judging, configuration, storage_pool):
        self.ordered_context, self.gate = ordered_context, gate
        self.teams, self.participants, self.projects = teams, participants, projects
        self.judging, self.configuration = judging, configuration
        self.storage_pool = storage_pool

    @contextmanager
    def locked(self, *, actor, event_id, team_id, action):
        # G acquires source+PII fences before the event and affected child rows.
        # The guard includes current host/origin/standing/servable/feature policy;
        # background cleanup uses its dedicated lifecycle authority, not a grant.
        with self.ordered_context(actor=actor, event_id=event_id, team_id=team_id, action=action) as event:
            self.gate.require(actor=actor, event=event, action=action)
            roster, leader_id = (), None
            if action in {"amend", "triage"}:
                event_authority.require(actor, event, "manage_hackathon")
                if team_id is not None:
                    roster, leader_id = self.teams.require_eligible_roster_locked(event_id=event_id, team_id=team_id)
            elif action in {"asset_worker", "deadline_lock"}:
                # Internal only: G's gate proves worker/lifecycle context. Before
                # publication the job separately uses asset_publish below.
                if team_id is not None:
                    roster, leader_id = self.teams.roster_locked(event_id=event_id, team_id=team_id)
            elif team_id is not None:
                roster, leader_id = self.teams.require_actor_locked(actor=actor, event_id=event_id,
                    team_id=team_id, action=action)
            else:
                self.participants.require_own_locked(actor=actor, event_id=event_id, action=action)
                roster = (actor.pk,)
            config = self.configuration.for_event_locked(event=event)
            yield SubmissionContext(event=event, team_id=team_id, member_ids=tuple(sorted(roster)),
                leader_id=leader_id, deadline=config.submission_deadline, grace_seconds=config.grace_seconds,
                late_policy=config.late_policy, managed=config.managed, budget_bytes=config.storage_budget_bytes,
                file_caps=getattr(config, "file_caps", {}), group_caps=getattr(config, "group_caps", {}))

    def lock_roster(self, *, context):
        self.teams.lock_roster_locked(event_id=context.event.pk, team_id=context.team_id)

    def validate_project(self, *, context, project, final):
        return self.projects.validate_locked(event_id=context.event.pk, team_id=context.team_id, project=project, final=final)

    def invalidate_snapshot(self, *, context, snapshot_id):
        self.judging.invalidate_snapshot_locked(event_id=context.event.pk, snapshot_id=snapshot_id)

    def invalidate_participant_asset_locked(self, *, context, member_id, asset_id, replacing):
        self.judging.invalidate_resume_locked(event_id=context.event.pk, member_id=member_id,
                                              asset_id=asset_id, replacing=replacing)

    def storage_pool_locked(self, *, context, asset, operation, bytes):
        self.storage_pool.apply_locked(event=context.event, asset_uuid=asset.public_id,
                                       operation=operation, bytes=bytes)
