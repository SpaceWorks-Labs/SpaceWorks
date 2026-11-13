"""Installed D runtime composed from the canonical A/B/C/E boundaries."""

from django.http import Http404
from django.utils import timezone

from apps.accounts.models import User
from apps.events import event_authority
from apps.events.programme_locks import fences, assert_lock_context, lock_authority
from apps.events.contracts.providers import ReadPurpose
from apps.events.hackathons.admission_transactions import require_programme
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.servability import is_servable
from .provider_values import ProgrammeValues
from .provider_subjects import ProgrammeSubjects


class JudgingProviders(ProgrammeValues, ProgrammeSubjects):
    fences = staticmethod(fences)
    assert_lock_context = staticmethod(assert_lock_context)

    def require_programme(self, event, *, gallery=False):
        if not is_servable(event.makerspace) or not module_enabled(event.makerspace, "events"):
            raise Http404
        require_programme(event)
        if gallery and not feature_enabled(event.makerspace, "events.project_gallery"):
            raise Http404

    def require_public_origin(self, event, request_context):
        from apps.makerspaces.origin_scope import object_in_staff_origin_scope
        # The HTTP middleware also enforces API-client origin/target policy.
        # A missing request must never become an internal public-origin bypass.
        if request_context is None or not object_in_staff_origin_scope(request_context, event):
            raise Http404

    def lock_authority(self, *, actor_id, event):
        actor = lock_authority(User.objects.filter(pk=actor_id).first(), event)
        # Shared configuration/roster parents precede D consent/round/result rows.
        from apps.events.hackathons.admission_models import HackathonConfig
        from apps.events.hackathons.admission_transactions import lock_domain_parents
        list(HackathonConfig.objects.select_for_update().filter(event=event))
        lock_domain_parents(event.pk)
        return actor

    def public_member_card(self, *, event_id, member_id, scope):
        from apps.events.contracts.photo_registration import public_member_card
        return public_member_card(event_id=event_id, member_id=member_id, scope=scope)

    def stream_asset(self, *, asset_id, snapshot_id, actor_id, purpose, request, reauthorize):
        from apps.events.submissions.api_runtime import runtime
        from apps.events.submissions.downloads import download_response
        adapters = runtime()
        reader = adapters.participant_reader if purpose == ReadPurpose.SPONSOR_RESUME else adapters.asset_reader
        if purpose == ReadPurpose.PUBLIC_GALLERY:
            from apps.events.submissions.read_policy import EventAssetReader
            class EntryPolicy:
                def require(self, **kwargs):
                    # The closure re-resolves the exact opaque entry, not merely
                    # some current publication for this same numeric asset.
                    item = reauthorize()
                    if item.asset_id != kwargs["asset"].pk or item.entry.snapshot_id != kwargs["snapshot_id"]:
                        raise Http404
                    return ()
            reader = EventAssetReader(policy=EntryPolicy(), bucket=adapters.storage.bucket)
        class Reader:
            def authorize_read(self, **kwargs):
                reauthorize()
                return reader.authorize_read(**kwargs)
        return download_response(request=request, reader=Reader(), storage_reader=adapters.storage_reader,
            actor_id=actor_id, asset_id=asset_id, snapshot_id=snapshot_id, purpose=purpose)

    def publish_retention_locked(self, *, event_id, first_published_at, locks):
        self.assert_lock_context(locks)
        if event_id != locks.event_id:
            raise Http404
        from apps.events.hackathons.admission_models import HackathonConfig
        from apps.events.submissions.models_assets import EventAssetUsage
        from apps.events.submissions.retention import anchor_locked
        from apps.audit.services import record
        config = HackathonConfig.objects.select_for_update().get(event_id=event_id)
        if config.first_results_published_at is None:
            config.first_results_published_at = first_published_at
            config.retention_anchor_at = min(config.retention_anchor_at, first_published_at) if config.retention_anchor_at else first_published_at
            config.save(update_fields=("first_results_published_at", "retention_anchor_at"))
            record(None, "event.hackathon.retention_anchored", makerspace=config.event.makerspace,
                   target=config, meta={"kind": "results"})
        usage, _ = EventAssetUsage.objects.get_or_create(event_id=event_id,
            defaults={"budget_bytes": config.storage_budget_bytes})
        usage = EventAssetUsage.objects.select_for_update().get(pk=usage.pk)
        anchor_locked(event=config.event, usage=usage, actor=None, kind="results", at=config.first_results_published_at)

    def shortlist_signals(self, *, event_id):
        from apps.events.mentoring.models_rounds import MentorNomination
        from django.db.models import Count
        # Explicit production nominations only. No identity or private note crosses D.
        rows = MentorNomination.objects.filter(event_id=event_id, round__practice_run_id=None,
            round__event_id=event_id).values("team_id").annotate(n=Count("mentor_id", distinct=True)).order_by("team_id")
        return tuple({"team_id": row["team_id"], "nominations": row["n"]} for row in rows)

    def notify_intent(self, notice_id):
        from .provider_notices import deliver
        return deliver(notice_id)
