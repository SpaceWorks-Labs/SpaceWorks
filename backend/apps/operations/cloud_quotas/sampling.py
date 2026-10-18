"""One remote page per tick; cursors and conservative concurrent deltas are durable."""
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone
from botocore.exceptions import BotoCoreError

from apps.operations.models import CloudObjectAccount, CloudObjectReservation, CloudObjectUsageReceipt, CloudUsageSample
from apps.storage_capabilities.accounting import usage_page
from apps.storage_capabilities.budget import storage_budget
from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.runtime import configured_contracts


def sample_storage_chunk(context):
    from apps.operations.cloud_jobs.contracts import ChunkResult
    from .storage import enabled
    if not enabled():
        return ChunkResult(True)
    contracts = configured_contracts()
    roles = sorted(contracts)
    index = context.checkpoint.get("role", 0)
    if type(index) is not int or not 0 <= index < len(roles):
        index = 0
    context.check()
    role = roles[index]
    contract = contracts[role]
    identity = contract.identity.fingerprint
    with transaction.atomic():
        row, _ = CloudObjectAccount.objects.get_or_create(identity=identity)
        row = CloudObjectAccount.objects.select_for_update().get(pk=identity)
        if not row.started_at or row.cursor.get("configuration") != contract.fingerprint:
            row.started_at, row.observed = timezone.now(), 0
            row.cursor = {"configuration": contract.fingerprint, "phase": "objects"}
            row.generation += 1
            row.save()
        generation, cursor = row.generation, row.cursor.copy()
    from .storage_clients import binding_client
    client = binding_client(role, contract)
    try:
        with storage_budget(deadline=context.deadline, check_active=context.check):
            if cursor["phase"] == "objects":
                page = usage_page(client, bucket=contract.identity.bucket, cursor=cursor.get("page"), page_size=50)
                amount = page.bytes_observed
                next_cursor = {**cursor, "page": page.continuation}
                if page.continuation is None:
                    next_cursor = {"configuration": contract.fingerprint, "phase": "multipart"}
                complete = False
            else:
                amount, next_cursor, complete = _multipart(client, contract, cursor)
        context.check()
    except (BotoCoreError, CapabilityError) as exc:
        if getattr(exc, "code", "") in {"storage_budget_exhausted", "storage_attempt_fenced"}:
            raise
        context.check()
        CloudObjectAccount.objects.filter(pk=identity, generation=generation).update(reason="storage_usage_unknown")
        return ChunkResult(False, {"role": index})
    finally:
        client.close()
    with transaction.atomic():
        row = CloudObjectAccount.objects.select_for_update().get(pk=identity)
        if row.generation != generation or row.cursor != cursor:
            raise CapabilityError("storage_sample_generation_changed")
        row.observed += amount
        row.cursor = next_cursor
        if complete:
            sample_started = row.started_at
            # Listings are not snapshots. Replay positive concurrent writes, even
            # if already listed; conservative double count cannot grant capacity.
            extra = CloudObjectUsageReceipt.objects.filter(bucket_alias=identity,
                operation="finalize", created_at__gte=row.started_at).aggregate(n=Sum("bytes"))["n"] or 0
            row.used, row.sampled_at, row.reason = row.observed + extra, timezone.now(), ""
            # URL expiry is not evidence that an in-flight upload has stopped.
            # Keep reservations charged until supervised drain/absence proof.
            row.started_at, row.cursor = None, {}
        row.save()
    if complete:
        _fold_drained_reservations(identity, sample_started)
    if complete:
        index += 1
    finished = index == len(roles)
    if finished:
        _publish()
        _database_sample()
    return ChunkResult(finished, {} if finished else {"role": index}, processed=1)


def _multipart(client, contract, cursor):
    bucket = contract.identity.bucket
    queued = cursor.get("uploads", [])
    if queued:
        upload = queued[0]
        params = {"Bucket": bucket, "Key": upload["Key"], "UploadId": upload["UploadId"], "MaxParts": 50}
        if cursor.get("part"):
            params["PartNumberMarker"] = cursor["part"]
        page = client.list_parts(**params)
        sizes = [p.get("Size") for p in page.get("Parts", [])]
        if any(type(s) is not int or s < 0 for s in sizes):
            raise CapabilityError("storage_incomplete_usage_unknown")
        updated = {**cursor}
        if page.get("IsTruncated"):
            marker = page.get("NextPartNumberMarker")
            if type(marker) is not int or marker <= cursor.get("part", 0):
                raise CapabilityError("storage_incomplete_pagination_invalid")
            updated["part"] = marker
        else:
            updated.pop("part", None)
            updated["uploads"] = queued[1:]
        return sum(sizes), updated, not updated.get("uploads") and updated.get("last", False)
    params = {"Bucket": bucket, "MaxUploads": 10}
    params.update(cursor.get("markers", {}))
    page = client.list_multipart_uploads(**params)
    updated = {"configuration": contract.fingerprint, "phase": "multipart",
               "uploads": [{"Key": u["Key"], "UploadId": u["UploadId"]} for u in page.get("Uploads", [])],
               "last": not page.get("IsTruncated", False)}
    if not updated["last"]:
        markers = {"KeyMarker": page.get("NextKeyMarker"), "UploadIdMarker": page.get("NextUploadIdMarker")}
        if not all(isinstance(v, str) and v for v in markers.values()) or markers == cursor.get("markers"):
            raise CapabilityError("storage_incomplete_pagination_invalid")
        updated["markers"] = markers
    return 0, updated, updated["last"] and not updated["uploads"]


def _publish():
    identities = {c.identity.fingerprint for c in configured_contracts().values()}
    rows = list(CloudObjectAccount.objects.filter(pk__in=identities))
    known = len(rows) == len(identities) and all(r.used is not None and not r.reason for r in rows)
    pending = CloudObjectReservation.objects.filter(state__in=["reserved", "writing", "uncertain"]).aggregate(n=Sum("bytes"))["n"] or 0
    _save_sample(metric="objects", scope="deployment", used=sum(r.used for r in rows) if known else None,
        uncertain=pending, sampled_at=min(r.sampled_at for r in rows) if known else timezone.now(),
        source="physical_inventory_with_concurrent_positive_deltas", reason_code="provider_external_usage_unknown")


def _database_sample():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        size = cursor.fetchone()[0]
    _save_sample(metric="database", scope="deployment", used=size,
        sampled_at=timezone.now(), source="postgres_database_size")


def _save_sample(**values):
    row = CloudUsageSample.objects.filter(metric=values["metric"], scope=values["scope"],
                                         makerspace=None).order_by("-sampled_at").first()
    if row:
        CloudUsageSample.objects.filter(pk=row.pk).update(**values)
    else:
        CloudUsageSample.objects.create(**values)


def _fold_drained_reservations(identity, started):
    from apps.backup.cloud_continuity import current_operation
    guard = current_operation()
    if guard is None:
        return
    from apps.backup.managed.models import ManagedCaptureState
    from apps.backup.managed.writers import assert_capture_drained
    state = ManagedCaptureState.objects.get(pk=1)
    if state.paused_by is None or started < state.paused_at:
        return
    assert_capture_drained(state.paused_by, guard)
    with transaction.atomic():
        CloudObjectAccount.objects.select_for_update().get(pk=identity)
        rows = CloudObjectReservation.objects.filter(account_id=identity, state__in=["reserved", "writing", "uncertain"], created_at__lte=state.paused_at)
        changed = rows.update(state="inventoried")
        from apps.audit import services as audit
        audit.record(None, "storage.reservations_reconciled", meta={
            "identity_fingerprint": identity, "reservations": changed, "drain_generation": state.generation})
