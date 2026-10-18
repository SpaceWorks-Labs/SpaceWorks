"""Closed-purpose, live asset authorization. A URL is a locator, never authority."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from django.utils import timezone

from apps.events.contracts.providers import ReadPurpose
from apps.makerspaces.private_upload_transport import ObjectLocator
from .asset_workflow import model_for
from .errors import SubmissionError

PURPOSES = frozenset({ReadPurpose.TEAM_ORIGINAL, ReadPurpose.OWNER_HISTORY,
    ReadPurpose.APPLICATION_REVIEW, ReadPurpose.JUDGE_SUBMISSION, ReadPurpose.ORGANIZER_ASSET,
    ReadPurpose.SPONSOR_TRACK, ReadPurpose.SPONSOR_RESUME, ReadPurpose.HELP_ATTACHMENT,
    ReadPurpose.PUBLIC_GALLERY})


class LiveAssetPolicy(Protocol):
    def require(self, *, actor_id, asset, snapshot_id, purpose) -> tuple[datetime | None, ...]:
        """Check live host/standing/feature/source, A team/roster or D exact
        assignment/window/conflict/track/public consent. D exclusively evaluates
        sponsor consent for this asset+hash. All denials uniform404. No cache.
        Return applicable authority expiry limits, never object keys.
        """
        ...


@dataclass(frozen=True)
class AuthorizedAsset:
    asset_id: int
    locator: ObjectLocator
    size: int
    mime: str
    filename: str
    limits: tuple[datetime | None, ...]


class EventAssetReader:
    def __init__(self, *, policy: LiveAssetPolicy, bucket, participant=False):
        self.policy, self.bucket, self.participant = policy, bucket, participant

    def authorize_read(self, *, actor_id, asset_id, snapshot_id, purpose):
        if not isinstance(purpose, ReadPurpose) or purpose not in PURPOSES:
            raise SubmissionError("not_found", 404)
        if self.participant and purpose not in {ReadPurpose.OWNER_HISTORY, ReadPurpose.SPONSOR_RESUME}:
            raise SubmissionError("not_found", 404)
        if not self.participant and purpose == ReadPurpose.SPONSOR_RESUME:
            raise SubmissionError("not_found", 404)
        asset = model_for(self.participant).objects.filter(pk=asset_id).first()
        if asset is None:
            raise SubmissionError("not_found", 404)
        if self.participant and purpose == ReadPurpose.OWNER_HISTORY and actor_id != asset.member_id:
            raise SubmissionError("not_found", 404)
        limits = self.policy.require(actor_id=actor_id, asset=asset, snapshot_id=snapshot_id, purpose=purpose)
        if snapshot_id is not None:
            if self.participant or not asset.snapshot_refs.filter(snapshot_id=snapshot_id,
                    snapshot__submission_id=asset.submission_id).exists():
                raise SubmissionError("not_found", 404)
        if asset.expired_at or asset.expires_at and timezone.now() >= asset.expires_at:
            raise SubmissionError("asset_expired", 410)
        if asset.state != "ready" or asset.scan_status not in {"clean", "skipped"}:
            raise SubmissionError("asset_not_ready", 409)
        return AuthorizedAsset(asset.pk,
            ObjectLocator(bucket=self.bucket, key=asset.object_key, version_id=asset.final_version_id or None),
            asset.actual_bytes, asset.canonical_mime, asset.original_filename, (*limits, asset.expires_at))
