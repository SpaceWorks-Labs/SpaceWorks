"""Atomically establish command ownership and its immutable evidence identity."""

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.evidence.models import EvidencePhoto, EvidenceObjectRetentionState, EvidenceUploadFinalization
from apps.evidence.services_upload import issue_upload, upload_maximum
from apps.evidence.storage import presigned_upload
from apps.hardware_requests.models_replay import ReplayCommand
from apps.hardware_requests.kiosk_online_commands import channel_meta
from apps.hardware_requests.replay_failures import ReplayFailure
from apps.hardware_requests.replay_fingerprint import fingerprint
from apps.hardware_requests.replay_records import age, audit_meta, ownership, result, scoped_targets
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from apps.makerspaces.storage_reservations import reserve
from apps.storage_capabilities.presigning import renewal_authorization
from apps.tenant_migration.gate_runtime import assert_write_allowed


def _upload_again(command, envelope):
    if command.evidence_id is None or command.state != ReplayCommand.State.PREPARED:
        return None
    # Cleanup and attachment acquire the space before the photo and receipt.
    # Keep that order while deciding whether this authorization is still live.
    space = Makerspace.objects.select_for_update(no_key=True).get(pk=command.makerspace_id)
    photo = EvidencePhoto.objects.select_for_update().get(pk=command.evidence_id)
    if EvidenceObjectRetentionState.objects.filter(evidence_id=command.evidence_id).exists():
        raise ReplayFailure("evidence_invalid")
    if EvidenceUploadFinalization.objects.filter(
        evidence_id=command.evidence_id, status=EvidenceUploadFinalization.Status.FINALIZED,
    ).exists():
        return None
    if photo.consumption_state == EvidencePhoto.ConsumptionState.CONSUMED:
        raise ReplayFailure("evidence_invalid")
    row = StorageQuotaReservation.objects.select_for_update().filter(object_key=photo.object_key).first()
    if row is None:
        # Pre-reservation commands need fresh admission for the SAME photo/key;
        # they must not obtain a database-free renewal of the old signature.
        maximum = upload_maximum(space, photo.size_bytes)
        row = reserve(space.pk, photo.object_key, maximum, bucket=settings.AWS_STORAGE_BUCKET_NAME,
                      staging_key="staging/" + photo.object_key, ttl=settings.EVIDENCE_URL_TTL_SECONDS,
                      kind="evidence")
    if (row.makerspace_id != space.pk or row.kind != "evidence" or row.converted
            or row.cleaning or row.released or row.expires_at <= timezone.now()
            or row.storage_endpoint != (settings.AWS_S3_ENDPOINT_URL or "")
            or row.bucket != settings.AWS_STORAGE_BUCKET_NAME
            or row.final_bucket != settings.AWS_STORAGE_BUCKET_NAME
            or row.staging_key != "staging/" + photo.object_key):
        raise ReplayFailure("evidence_invalid")
    with renewal_authorization(bucket=row.bucket, key=row.staging_key, max_bytes=row.size_bytes):
        upload = presigned_upload(photo.object_key, photo.content_type, max_bytes=row.size_bytes,
                                  exact_bytes=photo.size_bytes)
    # Signing can take time. Retain the unchanged byte debt until at least one
    # whole URL TTL AFTER signing, atomically, before returning the authorization.
    row.expires_at = max(row.expires_at, timezone.now() + timedelta(seconds=settings.EVIDENCE_URL_TTL_SECONDS))
    row.save(update_fields=["expires_at"])
    return {"evidence_id": photo.pk, "object_key": photo.object_key,
            "upload_url": upload["url"], "fields": upload.get("fields", {}),
            **({"method": upload["method"], "headers": upload.get("headers", {})} if "method" in upload else {})}


def prepare(identity, envelope):
    with transaction.atomic():
        station, lease, user = identity.live(envelope["kind"])
        assert_write_allowed(station.makerspace_id)
        expires = age(envelope, lease)
        owner = dict(station=station, station_session_id=identity.session_id,
                     client_command_id=envelope["client_command_id"])
        existing = ReplayCommand.objects.select_for_update().filter(**owner).first()
        if existing is not None:
            ownership(existing, identity, envelope)
            station, lease, user = identity.live(envelope["kind"])
            age(envelope, lease)
            data = result(existing)
            data["upload"] = _upload_again(existing, envelope)
            return data
        predecessor = None
        if envelope["sequence"] > 1:
            predecessor = ReplayCommand.objects.filter(
                station=station, station_session_id=identity.session_id,
                aggregate_id=envelope["aggregate_id"], sequence=envelope["sequence"] - 1,
                client_command_id=envelope["predecessor_client_id"], actor=user,
                operator_lease_id=lease.pk,
            ).first()
            if predecessor is None:
                raise ReplayFailure("predecessor_missing")
        try:
            with transaction.atomic():
                command = ReplayCommand.objects.create(
                    **owner, makerspace=station.makerspace, actor=user, operator_lease_id=lease.pk,
                    station_version=identity.version, payload_fingerprint=fingerprint(envelope),
                    operation_kind=envelope["kind"], operation_version=envelope["version"],
                    aggregate_id=envelope["aggregate_id"], sequence=envelope["sequence"],
                    predecessor=predecessor, client_created_at=envelope["client_created_at"], expires_at=expires,
                    **scoped_targets(station, user, envelope),
                )
        except IntegrityError:
            # Concurrent INSERT of the same owner waits for the first transaction,
            # then reuses its committed command/evidence. A stream-position collision
            # under a different owner ID remains a conflict.
            command = ReplayCommand.objects.select_for_update().filter(**owner).first()
            if command is None:
                raise ReplayFailure("idempotency_conflict") from None
            ownership(command, identity, envelope)
            station, lease, user = identity.live(envelope["kind"])
            age(envelope, lease)
            return {**result(command), "upload": _upload_again(command, envelope)}
        upload = None
        if envelope["evidence"] is not None:
            station, lease, user = identity.live(envelope["kind"])
            age(envelope, lease)
            # The owner row exists before presigning; any failure rolls back both rows.
            photo, upload = issue_upload(
                station.makerspace, actor=user, **envelope["evidence"],
                audit_action="kiosk.evidence_upload_issued", audit_meta=channel_meta(lease, "evidence_prepare"),
            )
            command.evidence = photo
            command.save(update_fields=["evidence", "updated_at"])
        audit.record(user, "kiosk.replay_prepared", makerspace=station.makerspace,
                     target=station, meta=audit_meta(command, lease))
        return {**result(command), "upload": upload}
