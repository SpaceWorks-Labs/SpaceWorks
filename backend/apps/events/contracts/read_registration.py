"""Live B asset purposes composed with A ownership and D consent/assignments."""

from django.http import Http404
from django.utils import timezone

from apps.accounts.models import User
from apps.events import event_authority
from apps.events.contracts.providers import ReadPurpose
from apps.events.hackathons.team_models import HackathonTeamMember
from apps.events.judging.models_scoring import JudgeAssignment
from apps.events.judging.ports import runtime
from apps.events.submissions.models_assets import HackathonParticipantAsset, SubmissionAsset


def judge_assignment(*, actor_id, event_id, snapshot_id):
    from apps.events.judging.conflicts import require_assignment
    actor = User.objects.filter(pk=actor_id).first()
    now = timezone.now()
    rows = JudgeAssignment.objects.filter(event_id=event_id, judge_role_assignment__member_id=actor_id,
        submission_snapshot_id=snapshot_id, round__state="open", state__in=("assigned", "scored")).select_related("round")
    for row in rows:
        if row.round.opens_at and row.round.opens_at > now or row.round.closes_at and row.round.closes_at <= now:
            continue
        try:
            require_assignment(actor, row, row.round)
        except Http404:
            continue
        return row
    raise Http404


class AssetPolicy:
    def require(self, *, actor_id, asset, snapshot_id, purpose):
        from apps.events.models_event import Event
        event = Event.objects.select_related("makerspace").get(pk=asset.event_id)
        ports = runtime()
        ports.require_programme(event, gallery=purpose == ReadPurpose.PUBLIC_GALLERY)
        if purpose == ReadPurpose.PUBLIC_GALLERY:
            # Public reads require D's per-request opaque-entry callback. B's
            # generic numeric reader cannot prove the original consent generation.
            raise Http404
        actor = User.objects.filter(pk=actor_id).first()
        if not event_authority._active(actor):
            raise Http404
        if purpose == ReadPurpose.OWNER_HISTORY and isinstance(asset, HackathonParticipantAsset):
            if actor_id != asset.member_id:
                raise Http404
            ports.owner_subject(event_id=event.pk, member_id=actor_id)
            return ()
        if isinstance(asset, HackathonParticipantAsset):
            if purpose != ReadPurpose.SPONSOR_RESUME:
                raise Http404
            from apps.events.judging.sponsors import track_scope
            from apps.events.judging.sponsor_consent_workflow import require_effective_for_asset
            for sponsor in ports.sponsors(event.pk):
                try:
                    if not track_scope(actor, event, sponsor.id):
                        continue
                    require_effective_for_asset(event_id=event.pk, member_id=asset.member_id,
                        sponsor_id=sponsor.id, asset_id=asset.pk, purpose="recruiting")
                except Http404:
                    continue
                return ()
            raise Http404
        if purpose in (ReadPurpose.TEAM_ORIGINAL, ReadPurpose.OWNER_HISTORY):
            if not HackathonTeamMember.objects.filter(event_id=event.pk, team_id=asset.team_id,
                    member_id=actor_id, state="active").exclude(team__state="disbanded").exists():
                raise Http404
            return ()
        if purpose == ReadPurpose.ORGANIZER_ASSET:
            event_authority.require(actor, event, "manage_hackathon")
            return ()
        if purpose == ReadPurpose.JUDGE_SUBMISSION:
            row = judge_assignment(actor_id=actor_id, event_id=event.pk, snapshot_id=snapshot_id)
            return (row.round.closes_at,)
        if purpose == ReadPurpose.SPONSOR_TRACK:
            from apps.events.judging.sponsors import require_track
            for sponsor in ports.sponsors(event.pk):
                try:
                    require_track(actor, event, sponsor.id, snapshot_id)
                except Http404:
                    continue
                return ()
        # Review/help attachment scopes need their actual subject binding. Never
        # treat an application-review permission as permission over team files.
        raise Http404


def admin_read_purpose(*, request, event_id, asset_id):
    from apps.events.models_event import Event
    event = Event.objects.select_related("makerspace").get(pk=event_id)
    actor = request.user
    if event_authority.can(actor, event, "manage_hackathon"):
        return ReadPurpose.ORGANIZER_ASSET, None
    snapshots = SubmissionAsset.objects.filter(pk=asset_id, event_id=event_id).values_list(
        "snapshot_refs__snapshot_id", flat=True)
    for snapshot_id in snapshots:
        try:
            judge_assignment(actor_id=actor.pk, event_id=event_id, snapshot_id=snapshot_id)
        except Http404:
            continue
        return ReadPurpose.JUDGE_SUBMISSION, snapshot_id
    raise Http404


def public_asset_resolver(*, request, public_token, public_asset_id):
    from apps.events.submissions.gallery_models import GalleryEntryAsset
    from apps.events.submissions.gallery_projection import public_event, live_entry
    event = public_event(public_token=public_token, request_context=request)
    item = GalleryEntryAsset.objects.select_related("entry").filter(public_id=public_asset_id,
        entry__event_id=event.pk).first()
    if item is None:
        raise Http404
    snapshot, consent = live_entry(item.entry)
    if item.asset_id not in snapshot.public_asset_ids or not consent.items.filter(
            asset_id=item.asset_id, active=True, generation=item.consent_generation).exists():
        raise Http404
    return item.asset_id, item.entry.snapshot_id
