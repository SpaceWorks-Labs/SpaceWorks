"""B/C -> D value projections. Never expose mutable models across the ports."""

from django.db.models import Count, F, Q
from django.http import Http404
from django.utils import timezone

from apps.events.contributions.authority import active_entitlements
from apps.events.contributions.models_roles import EventRoleAssignment, EventSponsor, EventSponsorTrack
from apps.events.submissions.models_projects import HackathonSubmission, SubmissionSnapshot, SnapshotTrack
from apps.events.submissions.models_assets import HackathonParticipantAsset, EventAssetUsage, SubmissionAsset
from .ports import Judge, ParticipantAsset, PublicLink, Snapshot, Sponsor

PROJECT_STATES = ("submitted", "locked", "under_review", "judged")


class ProgrammeValues:
    def snapshot(self, snapshot_id):
        row = SubmissionSnapshot.objects.select_related("submission", "submission__team").filter(pk=snapshot_id).first()
        if row is None:
            raise Http404
        project, data = row.submission, row.project
        assets = tuple(row.asset_refs.order_by("pk").values_list("asset_id", flat=True))
        links = tuple(PublicLink(id=link.link_id, kind=link.kind, url=link.url)
                      for link in row.link_refs.order_by("pk"))
        usage = EventAssetUsage.objects.filter(event_id=project.event_id).first()
        return Snapshot(id=row.pk, event_id=project.event_id, team_id=project.team_id,
            member_ids=tuple(row.sealed_member_ids),
            track_ids=tuple(row.track_refs.values_list("track_id", flat=True)),
            prize_ids=tuple(row.prize_refs.values_list("prize_id", flat=True)),
            title=data.get("title", ""), description=data.get("description", ""),
            content_sha256=row.content_sha256, current=project.current_snapshot_id == row.pk,
            eligible=project.state in PROJECT_STATES and project.triage == "eligible",
            metadata_public=data.get("public_requested") is True,
            public_asset_ids=tuple(row.asset_refs.filter(public_requested=True).values_list("asset_id", flat=True)),
            public_links=tuple(link for link in links if link.id in set(row.link_refs.filter(
                public_requested=True).values_list("link_id", flat=True))),
            expires_at=usage.expires_at if usage else None, room=project.team.zone,
            judge_asset_ids=assets, judge_links=links)

    def snapshots(self, event_id):
        ids = HackathonSubmission.objects.filter(event_id=event_id,
            current_snapshot__isnull=False).order_by("pk").values_list("current_snapshot_id", flat=True)
        return tuple(self.snapshot(pk) for pk in ids)

    def track_occupancy_locked(self, *, event_id, track_ids, exclude_team_id, locks):
        self.assert_lock_context(locks)
        if event_id != locks.event_id:
            raise Http404
        rows = SnapshotTrack.objects.filter(track_id__in=track_ids,
            snapshot__submission__event_id=event_id, snapshot_id=F("snapshot__submission__current_snapshot_id"),
            snapshot__submission__state__in=PROJECT_STATES).exclude(
                snapshot__submission__triage="ineligible").exclude(snapshot__submission__team_id=exclude_team_id)
        counts = {row["track_id"]: row["n"] for row in rows.values("track_id").annotate(n=Count("pk"))}
        return {pk: counts.get(pk, 0) for pk in track_ids}

    def judge(self, role_assignment_id):
        role = EventRoleAssignment.objects.filter(pk=role_assignment_id, role="judge").first()
        if role is None:
            raise Http404
        sources = active_entitlements(event_id=role.event_id).filter(role_assignment_id=role.pk, source_kind="role",
            permissions__contains=["judge"], event_id=role.event_id)
        # A display role or its grant's cached union is not current authority.
        # Each judge value is one role source, so disjoint source scopes never widen.
        source = sources.first()
        return Judge(role_assignment_id=role.pk, event_id=role.event_id, member_id=role.member_id,
            active=source is not None, track_ids=tuple(source.track_ids) if source else ())

    def judges(self, event_id):
        return tuple(self.judge(pk) for pk in EventRoleAssignment.objects.filter(
            event_id=event_id, role="judge").order_by("pk").values_list("pk", flat=True))

    def sponsor(self, sponsor_id):
        row = EventSponsor.objects.filter(pk=sponsor_id).first()
        if row is None:
            raise Http404
        tracks = EventSponsorTrack.objects.filter(sponsor=row, event_id=row.event_id,
            track__event_id=row.event_id).order_by("track_id").values_list("track_id", flat=True)
        return Sponsor(id=row.pk, event_id=row.event_id, name=row.label, active=row.active,
                       track_ids=tuple(tracks), disclosure_revision=row.version)

    def sponsors(self, event_id):
        return tuple(self.sponsor(pk) for pk in EventSponsor.objects.filter(
            event_id=event_id).order_by("pk").values_list("pk", flat=True))

    def sponsor_rep_tracks(self, *, event_id, sponsor_id, actor_id):
        sources = active_entitlements(event_id=event_id).filter(event_id=event_id, grant__user_id=actor_id,
            source_kind="role", role_assignment__role="sponsor_rep", role_assignment__sponsor_id=sponsor_id,
            permissions__contains=["view_sponsor_track"])
        return tuple(sorted({pk for ids in sources.values_list("track_ids", flat=True) for pk in ids}))

    def participant_asset(self, asset_id):
        row = HackathonParticipantAsset.objects.filter(pk=asset_id).first()
        if row is None:
            raise Http404
        current = bool(row.ready_at) and not HackathonParticipantAsset.objects.filter(event_id=row.event_id,
            member_id=row.member_id, purpose="resume", ready_at__isnull=False).filter(
                Q(ready_at__gt=row.ready_at) | Q(ready_at=row.ready_at, pk__gt=row.pk)).exists()
        return ParticipantAsset(id=row.pk, event_id=row.event_id, member_id=row.member_id,
            sha256=row.sha256, state="expired" if row.expired_at else row.state,
            expires_at=row.expires_at, current=current, purpose=row.purpose)

    def public_asset(self, *, event_id, asset_id):
        row = SubmissionAsset.objects.filter(pk=asset_id, event_id=event_id).first()
        if row is None:
            raise Http404
        expired = row.expired_at or row.expires_at and row.expires_at <= timezone.now()
        return {"id": row.pk, "kind": row.kind, "mime": row.canonical_mime,
                "bytes": row.actual_bytes, "sha256": row.sha256, "state": "expired" if expired else row.state}
