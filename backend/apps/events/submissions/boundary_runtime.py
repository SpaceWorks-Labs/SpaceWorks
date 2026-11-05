"""Production submission boundary over the canonical A/C/D source services."""
from contextlib import ExitStack, contextmanager
from django.db import transaction
from django.utils import timezone
from apps.events import event_authority
from apps.events.programme_locks import event_scopes, fences, lock_event, lock_authority, current_locks
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .boundary_adapter import ProgrammeReceipts
from .errors import SubmissionError
from .ports import SubmissionContext, install_boundary


# #178-#180: the stage editor, shortlists, extensions and bulk triage need the hackathon manager,
# the same authority that edits the submission window.
STAFF_STAGE_ACTIONS = frozenset({"stage_edit", "stage_shortlist", "stage_extension"})


class ProgrammeBoundary(ProgrammeReceipts):
    @contextmanager
    def locked(self, *, actor, event_id, team_id, action):
        from apps.events.hackathons.admission_transactions import require_programme, lock_domain_parents
        from apps.events.submissions.pii import prepare_documents
        from apps.makerspaces import limits
        from apps.events.models import Event
        accounts = (actor.pk,) if actor is not None else ()
        try:
            tenants, accounts = event_scopes(event_id=event_id, account_ids=accounts)
        except Event.DoesNotExist:
            # An unknown event is a 404 for every submission route, never a server error.
            raise SubmissionError("not_found", 404) from None
        with prepare_documents(event_id), ExitStack() as stack:
            for pk in tenants:
                stack.enter_context(boundary_tenant_write(pk))
            stack.enter_context(transaction.atomic())
            stack.enter_context(fences(tenant_ids=tenants, account_ids=accounts))
            event = lock_event(event_id=event_id, account_ids=accounts)
            actor = lock_authority(actor, event)
            config = require_programme(event)
            lock_domain_parents(event_id)
            internal = action in {"asset_worker", "deadline_lock", "stage_reminder"}
            if actor is None and not internal:
                raise SubmissionError("not_found", 404)
            if actor is not None and not event_authority._active(actor):
                raise SubmissionError("not_found", 404)
            members, leader = (), None
            if action in {"amend", "triage", "admin_read"} | STAFF_STAGE_ACTIONS:
                event_authority.require(actor, event, "manage_hackathon")
                if team_id is not None:
                    members, leader = self.roster(event_id, team_id, eligible=False)
            elif team_id is not None:
                members, leader = self.roster(event_id, team_id, eligible=not internal and action != "project_read")
                if not internal and actor.pk not in members:
                    raise SubmissionError("not_found", 404)
            elif not internal:
                self.participant(event, actor)
                members = (actor.pk,)
            # #178: the context window is the LAST stage's (the end of all submission); each stage's own
            # window is checked by the submit path.
            from .models_stages import SubmissionStage
            last = SubmissionStage.objects.filter(event=event).order_by("-position").first()
            deadline, grace, late = ((last.deadline, last.grace_minutes, last.late_policy) if last else
                                     (config.submission_deadline, config.submission_grace_minutes, config.late_policy))
            yield SubmissionContext(event=event, team_id=team_id, member_ids=members, leader_id=leader,
                deadline=deadline or event.ends_at, grace_seconds=grace*60,
                late_policy=late, managed=not limits.is_self_host(), budget_bytes=config.storage_budget_bytes,
                upload_policy=config.upload_policy, upload_policy_version=config.upload_policy_version)

    def roster(self, event_id, team_id, *, eligible):
        from apps.events.hackathons.team_models import HackathonTeam
        team = HackathonTeam.objects.select_for_update().filter(pk=team_id, event_id=event_id).first()
        if team is None or team.state == "disbanded":
            raise SubmissionError("not_found", 404)
        if eligible:
            from apps.events.hackathons.admission_workflow import require_team_eligible
            require_team_eligible(team_id=team_id, event_id=event_id, at=timezone.now())
        return tuple(team.memberships.filter(state="active").order_by("member_id").values_list("member_id", flat=True)), team.leader_id

    def participant(self, event, actor):
        from apps.events.registration_access import require_registration_access
        from apps.events.hackathons.admission_models import HackathonApplication
        from apps.events.contributions.models_roles import EventRoleAssignment
        require_registration_access(event, actor)
        if not (HackathonApplication.objects.filter(event=event, member=actor,
                state__in=("submitted", "offered", "confirmed", "waitlisted")).exists()
                or EventRoleAssignment.objects.filter(event=event, member=actor,
                    state__in=("applied", "approved"), imported_inert=False).exists()):
            raise SubmissionError("not_found", 404)

    def lock_roster(self, *, context):
        from apps.events.hackathons.team_workflow import lock_roster_locked
        lock_roster_locked(team_id=context.team_id, locks=current_locks(context.event.pk))

    def validate_project(self, *, context, project, final):
        from .project_adapter import validate_project
        return validate_project(context=context, project=project, final=final)

    def invalidate_snapshot(self, *, context, snapshot_id):
        from apps.events.judging.lifecycle import invalidate_snapshot_locked
        invalidate_snapshot_locked(event=context.event, snapshot_id=snapshot_id,
            locks=current_locks(context.event.pk), actor=None)

    def invalidate_participant_asset_locked(self, *, context, member_id, asset_id, replacing):
        from apps.events.judging.sponsor_consent_workflow import revoke_asset_locked
        from .models_assets import HackathonParticipantAsset
        ids = [asset_id]
        if replacing:
            ids += list(HackathonParticipantAsset.objects.filter(event=context.event,
                member_id=member_id).exclude(pk=asset_id).values_list("pk", flat=True))
        for pk in sorted(set(ids)):
            revoke_asset_locked(event_id=context.event.pk, asset_id=pk, locks=current_locks(context.event.pk))

    def storage_pool_locked(self, *, context, asset, operation, bytes):
        from apps.makerspaces.storage_events_programme import EventAssetStoragePool
        EventAssetStoragePool().apply_locked(event=context.event, asset_uuid=asset.public_id,
            operation=operation, bytes=bytes)


_provider = ProgrammeBoundary()


def install():
    install_boundary(_provider)
