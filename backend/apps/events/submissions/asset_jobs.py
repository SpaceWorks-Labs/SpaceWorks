"""Leased, retryable out-of-transaction workers. A sweeper may invoke run_asset.

All state writes re-enter the live boundary. Storage calls never hold row locks.
The deployment must schedule this persisted work even when Celery beat is absent.
"""
from datetime import timedelta
from uuid import uuid4
import hashlib
import tempfile
import logging
from copy import copy

from django.utils import timezone

from apps.audit.services import record
from apps.maker_formats.upload_policy import validate_upload
from apps.maker_formats.images import canonical_image
from apps.maker_formats.errors import FormatError
from apps.maker_formats.zip_listing import manifest_json
from .asset_workflow import model_for
from .errors import SubmissionError
from .ports import boundary
from .quota import usage_locked, charge, release_after_cleanup, reserve_canonical_difference
from .scanning import scan
from .probing import probe_video
from .storage_promotion import existing, promote
from .storage_cleanup import delete_keys

TERMINAL = {"aborted", "rejected", "quarantined", "expiring", "expired", "deleting"}
logger = logging.getLogger(__name__)


class AssetJob:
    def __init__(self, *, actor, event_id, team_id, asset_id, participant, storage):
        self.actor, self.event_id, self.team_id = actor, event_id, team_id
        self.asset_id, self.participant, self.storage = asset_id, participant, copy(storage)
        self.token = uuid4()

    def edit(self, callback, *, acquire=False, publish=False):
        with boundary().locked(actor=self.actor, event_id=self.event_id, team_id=self.team_id,
                               action="asset_publish" if publish else "asset_worker") as ctx:
            asset = model_for(self.participant).objects.select_for_update().get(pk=self.asset_id, event_id=self.event_id)
            work = type(asset.work).objects.select_for_update().get(pk=asset.work.pk)
            now = timezone.now()
            if acquire:
                if work.lease_until and work.lease_until > now:
                    raise SubmissionError("lease_lost", 409)
                work.lease_token, work.state = self.token, "processing"
                work.attempts += 1
            elif work.lease_token != self.token or not work.lease_until or work.lease_until <= now:
                raise SubmissionError("lease_lost", 409)
            work.lease_until = now + timedelta(minutes=5)
            result = callback(asset, work, ctx)
            asset.save()
            work.save()
            return result

    def run(self, *, scan_options, sandbox_command=()):
        asset = self.edit(lambda a, w, c: a, acquire=True)
        last_renewed = timezone.now()
        def heartbeat():
            nonlocal last_renewed
            if timezone.now() - last_renewed >= timedelta(seconds=30):
                self.edit(lambda a, w, c: None)
                last_renewed = timezone.now()
        self.storage.on_progress = heartbeat
        try:
            if asset.state in TERMINAL:
                return self.cleanup(asset)
            if asset.state == "reserved":
                descriptor, upload_id, part_size = self.storage.initialize(asset, now=timezone.now())
                def started(a, w, ctx):
                    a.multipart_upload_id, a.part_size, a.state = upload_id, part_size, "uploading"
                    from apps.makerspaces.storage_events_programme import refresh_obligation_locked
                    refresh_obligation_locked(a)
                    record(self.actor, "event.asset_uploading", makerspace=ctx.event.makerspace, target=a)
                    w.state, w.lease_token, w.lease_until = "waiting", None, None
                self.edit(started)
                return descriptor
            if asset.state == "uploading":
                self.edit(lambda a, w, c: _done(w, "waiting"))
                return None
            if asset.state == "ready":
                return self.cleanup(asset, temporary_only=True)
            frozen = self._verification(asset)
            reader = self.storage.reader(frozen)
            result, spec = validate_upload(reader, extension=asset.extension,
                group="fab-2d" if self.participant else asset.kind, subtype=asset.subtype, effective_cap=asset.effective_cap)
            self.edit(lambda a, w, c: None)  # Renew between bounded phases.
            digest = self.storage.digest(frozen)
            scanned = scan(reader, **scan_options)
            if scanned.status == "infected":
                def infected(a, w, ctx):
                    a.original_sha256, a.sha256, a.actual_bytes = digest, digest, frozen.size
                    a.scan_backend, a.scan_status, a.scan_version = scanned.backend, scanned.status, scanned.version
                    a.scanned_at, a.state = timezone.now(), "quarantined"
                    a.expired_at, a.version = timezone.now(), a.version + 1
                    record(self.actor, "event.asset_quarantined", makerspace=ctx.event.makerspace, target=a,
                           meta={"sha256": digest, "bytes": frozen.size})
                self.edit(infected)
                raise SubmissionError("asset_infected", 400)
            canonical, metadata = None, {}
            if spec.checker == "image":
                canonical = canonical_image(b"".join(reader.chunks()), expected_mime=result.mime)
                digest = hashlib.sha256(canonical).hexdigest()
            if spec.group == "video":
                with tempfile.TemporaryDirectory(prefix="sw-event-probe-") as tmp:
                    from pathlib import Path
                    path = Path(tmp) / ("input." + asset.extension)
                    with path.open("wb") as handle:
                        for chunk in reader.chunks():
                            handle.write(chunk)
                    metadata = probe_video(path, sandbox_command=sandbox_command)
            def promoting(a, w, ctx):
                if canonical is not None:
                    extra = max(0, len(canonical) - a.reserved_bytes)
                    reserve_canonical_difference(usage_locked(ctx), a, len(canonical),
                                                 group_cap_bytes=ctx.group_caps.get(a.kind))
                    if extra:
                        boundary().storage_pool_locked(context=ctx, asset=a, operation="reserve_canonical", bytes=extra)
                a.state = "promoting"
                record(self.actor, "event.asset_promoting", makerspace=ctx.event.makerspace, target=a)
            self.edit(promoting, publish=True)
            final = promote(self.storage, source=frozen, target_key=asset.object_key,
                            sha256=digest, canonical_bytes=canonical, mime=result.mime)
            def ready(a, w, ctx):
                if a.state != "promoting" or a.claim != asset.claim or a.generation != asset.generation:
                    raise SubmissionError("lease_lost", 409)
                usage = usage_locked(ctx)
                if a.expired_at or usage.expires_at and usage.expires_at <= timezone.now():
                    raise SubmissionError("asset_expired", 410)
                charge(usage, a, final.size)
                boundary().storage_pool_locked(context=ctx, asset=a, operation="charge", bytes=final.size)
                a.state, a.actual_bytes, a.sha256 = "ready", final.size, digest
                a.original_sha256 = self.storage_digest  # Hash saved outside locks.
                a.canonical_mime, a.manifest, a.media_metadata = result.mime, manifest_json(result.manifest), metadata
                a.subtype = result.subtype
                a.scan_backend, a.scan_status, a.scan_version = scanned.backend, scanned.status, scanned.version
                a.scanned_at, a.ready_at, a.final_version_id = timezone.now(), timezone.now(), final.version_id or ""
                a.expires_at = usage.expires_at
                a.version += 1
                if self.participant:
                    boundary().invalidate_participant_asset_locked(context=ctx, member_id=a.member_id,
                                                                  asset_id=a.pk, replacing=True)
                record(self.actor, "event.asset_ready", makerspace=ctx.event.makerspace, target=a,
                       meta={"bytes": final.size, "sha256": digest})
                _done(w, "pending")  # Temporary-copy cleanup must survive a crash.
            self.storage_digest = self.storage.digest(frozen)
            self.edit(ready, publish=True)
            return {"asset_id": asset.pk, "state": "ready"}
        except (SubmissionError, FormatError) as exc:
            if exc.code == "lease_lost":
                raise
            logger.warning("event_asset_attempt_failed", extra={"event_id": self.event_id,
                "asset_id": self.asset_id, "participant_asset": self.participant, "failure_code": exc.code})
            def failed(a, w, ctx, exc=exc):
                a.failure_code = exc.code
                if exc.status < 500:
                    a.state = "quarantined" if exc.code == "asset_infected" else "rejected"
                    a.expired_at = a.expired_at or timezone.now()
                w.last_code, w.next_attempt_at = exc.code, timezone.now() + timedelta(minutes=5)
                _done(w, "pending")
                record(self.actor, "event.asset_attempt_failed", makerspace=ctx.event.makerspace, target=a,
                       meta={"code": exc.code, "retryable": exc.status >= 500})
            self.edit(failed)
            raise SubmissionError(exc.code, exc.status) from exc

    def _verification(self, asset):
        frozen = existing(self.storage, asset.verification_key)
        if frozen:
            if frozen.size != asset.declared_bytes:
                raise SubmissionError("upload_size_mismatch", 413)
            return frozen
        if asset.state == "copying":
            from .api_runtime import runtime
            provider = runtime().saved_resume_provider
            prepared = provider.prepare(actor_id=asset.member_id, saved_asset_id=asset.work.saved_asset_id,
                                         saved_detail_version=asset.work.saved_detail_version)
            # P rechecks owner/key/readiness/version before and after server copy.
            # It returns no source key to HTTP or the Events database.
            provider.copy_to_event(prepared=prepared, event_id=asset.event_id,
                                   asset_id=asset.pk, target_key=asset.verification_key)
            frozen = self.storage.head(asset.verification_key)
            if frozen.size != asset.declared_bytes or self.storage.digest(frozen) != prepared.sha256:
                raise SubmissionError("saved_detail_changed", 409)
            return frozen
        # Reconcile a completed multipart after crash without reusing client proof.
        source = existing(self.storage, asset.staging_key)
        if source is None:
            source = self.storage.complete(asset)
        if source.size != asset.declared_bytes:
            raise SubmissionError("upload_size_mismatch", 413)
        frozen = self.storage.freeze(source, asset.verification_key)
        def verified(a, w, ctx):
            a.state, a.source_version_id, a.source_etag = "validating", source.version_id or "", source.etag
            a.verification_version_id = frozen.version_id or ""
            record(self.actor, "event.asset_validating", makerspace=ctx.event.makerspace, target=a)
        self.edit(verified)
        return frozen

    def cleanup(self, asset, *, temporary_only=False):
        keys = [asset.staging_key, asset.verification_key]
        if not temporary_only:
            keys.append(asset.object_key)
        # A staging POST can recreate bytes until its final signature expires.
        if timezone.now() < asset.last_activity_at + timedelta(minutes=16):
            raise SubmissionError("write_grant_still_live", 503)
        delete_keys(self.storage, keys)
        def cleaned(a, w, ctx):
            usage = usage_locked(ctx)
            released = a.reserved_bytes + (a.charged_bytes if not temporary_only else 0)
            release_after_cleanup(usage, a, final_deleted=not temporary_only)
            if released:
                boundary().storage_pool_locked(context=ctx, asset=a,
                    operation="release_all" if not temporary_only else "release_temporary", bytes=released)
            if not temporary_only:
                a.deleted_at = a.deleted_at or timezone.now()
                a.expired_size_bytes = a.actual_bytes
                a.state = "expired" if a.state in {"expiring", "expired"} else a.state
            _done(w, "verify_absence")
            w.next_attempt_at = timezone.now() + timedelta(hours=6)
            record(self.actor, "event.asset_bytes_deleted", makerspace=ctx.event.makerspace, target=a,
                   meta={"temporary_only": temporary_only})
        self.edit(cleaned)


def _done(work, state):
    work.state, work.lease_token, work.lease_until = state, None, None
