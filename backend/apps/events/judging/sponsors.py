"""Read-only sponsor projections and live résumé gateways, never a member roster."""

from django.http import Http404

from apps.events import event_authority
from apps.events.contracts.providers import ReadPurpose
from .ports import runtime
from .sponsor_consent_workflow import require_effective_for_asset


def track_scope(actor, event, sponsor_id):
    from django.contrib.auth import get_user_model
    from apps.events.models import Event
    # Streams call this repeatedly: previously loaded User/Event objects are NOT live policy.
    current = Event.objects.select_related("makerspace").filter(pk=event.pk).first()
    actor = get_user_model().objects.filter(pk=actor.pk).first()
    if current is None or actor is None:
        raise Http404
    runtime().require_programme(current)
    if not event_authority.can(actor, current, "view_sponsor_track"):
        raise Http404
    sponsor = runtime().sponsor(sponsor_id)
    if sponsor.event_id != current.pk or not sponsor.active:
        raise Http404
    tracks = set(runtime().sponsor_rep_tracks(event_id=current.pk, sponsor_id=sponsor_id, actor_id=actor.pk))
    return tracks & set(sponsor.track_ids)


def require_track(actor, event, sponsor_id, snapshot_id):
    scope = track_scope(actor, event, sponsor_id)
    snapshot = runtime().snapshot(snapshot_id)
    if (snapshot.event_id != event.pk or not snapshot.current or not snapshot.eligible
            or not set(snapshot.track_ids) & scope):
        raise Http404
    return snapshot


def submissions(actor, event, sponsor_id):
    tracks = track_scope(actor, event, sponsor_id)
    if not tracks:
        raise Http404
    from .models_consent import ParticipantSponsorResumeConsent
    from .errors import ProgrammeError
    result = []
    for snapshot in runtime().snapshots(event.pk):
        if not (snapshot.event_id == event.pk and snapshot.current and snapshot.eligible and set(snapshot.track_ids) & tracks):
            continue
        resumes = []
        grants = ParticipantSponsorResumeConsent.objects.filter(event=event, sponsor_id=sponsor_id,
            member_id__in=snapshot.member_ids, state="granted").order_by("pk")
        for grant in grants:
            try:
                require_effective_for_asset(event_id=event.pk, member_id=grant.member_id, sponsor_id=sponsor_id,
                    asset_id=grant.participant_asset_id, purpose="recruiting")
            except (Http404, ProgrammeError):
                continue
            resumes.append({"asset_id": grant.participant_asset_id,
                "download_url": f"/api/v1/admin/events/{event.pk}/sponsors/{sponsor_id}/resumes/{grant.participant_asset_id}/"})
        result.append({"snapshot_id": snapshot.id, "title": snapshot.title, "description": snapshot.description,
            "track_ids": sorted(set(snapshot.track_ids) & tracks), "asset_ids": list(snapshot.judge_asset_ids),
            "links": [{"kind": link.kind, "url": link.url} for link in snapshot.judge_links], "resumes": resumes})
    return result


def resume_download(actor, event, sponsor_id, asset_id, request):
    def authorize():
        tracks = track_scope(actor, event, sponsor_id)
        asset = runtime().participant_asset(asset_id)
        if asset.event_id != event.pk or not any(s.event_id == event.pk and s.current and s.eligible
                and asset.member_id in s.member_ids and set(s.track_ids) & tracks
                for s in runtime().snapshots(event.pk)):
            raise Http404
        require_effective_for_asset(event_id=event.pk, member_id=asset.member_id, sponsor_id=sponsor_id,
                                    asset_id=asset_id, purpose="recruiting")
    authorize()
    return runtime().stream_asset(asset_id=asset_id, snapshot_id=None, actor_id=actor.pk,
                                   purpose=ReadPurpose.SPONSOR_RESUME, request=request, reauthorize=authorize)
