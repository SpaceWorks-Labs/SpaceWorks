"""Authenticated inspection and a real concurrent create-only qualification probe."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import Barrier, Event
import uuid

from botocore.exceptions import BotoCoreError, ClientError

from .contracts import CapabilityError
from .budget import checkpoint

UNSUPPORTED = frozenset({
    "NotImplemented", "501", "MethodNotAllowed", "UnsupportedOperation", "XNotImplemented",
})


def _code(exc):
    return str(exc.response.get("Error", {}).get("Code", ""))


def inspect_bucket(client, contract):
    bucket = contract.identity.bucket
    facts = {}
    try:
        checkpoint()
        client.head_bucket(Bucket=bucket)
        try:
            checkpoint()
            response = client.get_bucket_versioning(Bucket=bucket)
        except ClientError as exc:
            if _code(exc) not in UNSUPPORTED or contract.versioning != "never_versioned":
                raise
            # Explicit operator declaration, corroborated by authenticated access;
            # unsupported API alone NEVER makes an unknown bucket never-versioned.
            facts["versioning_source"] = "declared_without_version_api"
            response = {}
        versioning = {"Enabled": "enabled", "Suspended": "suspended"}.get(response.get("Status"))
        if response.get("Status") is not None and versioning is None:
            raise CapabilityError("storage_versioning_unknown")
        if versioning is None:
            versioning = "never_versioned"
        if versioning in {"enabled", "suspended"} and contract.versioning == "never_versioned":
            raise CapabilityError("storage_history_observed_in_never_versioned_bucket")
        if contract.versioning == "unknown" or versioning != contract.versioning:
            raise CapabilityError("storage_versioning_mismatch")
        facts["versioning"] = versioning
        if contract.versioning == "never_versioned":
            try:
                checkpoint()
                page = client.list_object_versions(Bucket=bucket, MaxKeys=1)
                if page.get("DeleteMarkers") or any(item.get("VersionId") not in {None, "null"}
                                                   for item in page.get("Versions", ())):
                    raise CapabilityError("storage_history_observed_in_never_versioned_bucket")
            except ClientError as exc:
                if _code(exc) not in UNSUPPORTED:
                    raise
        if contract.list_delete_versions is True:
            checkpoint()
            client.list_object_versions(Bucket=bucket, Prefix="spaceworks-capability-probes/", MaxKeys=1)
            facts["list_delete_versions"] = True
        if contract.object_lock is True:
            checkpoint()
            config = client.get_object_lock_configuration(Bucket=bucket)["ObjectLockConfiguration"]
            if config.get("ObjectLockEnabled") != "Enabled":
                raise CapabilityError("storage_object_lock_mismatch")
            facts["object_lock_configured"] = True
        if contract.cors_management is True:
            try:
                checkpoint()
                client.get_bucket_cors(Bucket=bucket)
            except ClientError as exc:
                if _code(exc) != "NoSuchCORSConfiguration":
                    raise
            # GET access is diagnostic; it does not prove write/provision authority.
            facts["cors_readable"] = True
    except CapabilityError:
        raise
    except (BotoCoreError, ClientError, KeyError):
        raise CapabilityError("storage_probe_unknown") from None
    return facts


def probe_conditional_create(client, *, bucket, prefix="spaceworks-capability-probes/", never_versioned=False):
    """Exactly one concurrent winner, unchanged bytes, and a refused later replay.

    Use a private, empty, run-specific prefix in the actual API/account. Finally
    deletes all exact-key versions; failed cleanup invalidates the qualification.
    Object Lock qualification uses a separate independently provisioned sink.
    """
    from .deletion import delete_exact_key

    if prefix != "spaceworks-capability-probes/":
        raise CapabilityError("storage_probe_prefix_invalid")
    key = f"{prefix}{uuid.uuid4().hex}"
    payloads = (uuid.uuid4().bytes, uuid.uuid4().bytes)
    start = Barrier(2, timeout=10)
    history_seen = Event()

    def put(payload, *, concurrent=False):
        if concurrent:
            start.wait()
        try:
            checkpoint()
            result = client.put_object(Bucket=bucket, Key=key, Body=payload, IfNoneMatch="*")
            if never_versioned and result.get("VersionId") not in {None, "null"}:
                history_seen.set()
                raise CapabilityError("storage_history_observed_in_never_versioned_bucket")
            return payload
        except ClientError as exc:
            if (_code(exc) in {"PreconditionFailed", "ConditionalRequestConflict"}
                or exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") in {409, 412}):
                return None
            raise

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(copy_context().run, put, payload, concurrent=True)
                       for payload in payloads]
            winners = [result for future in futures if (result := future.result()) is not None]
        if len(winners) != 1:
            raise CapabilityError("storage_conditional_create_unproven")
        if _read(client, bucket, key) != winners[0] or put(b"replay") is not None:
            raise CapabilityError("storage_conditional_create_unproven")
        if _read(client, bucket, key) != winners[0]:
            raise CapabilityError("storage_conditional_create_unproven")
    except CapabilityError:
        raise
    except (BotoCoreError, ClientError, OSError):
        raise CapabilityError("storage_conditional_create_unknown") from None
    finally:
        try:
            delete_exact_key(client, bucket=bucket, key=key,
                             never_versioned=never_versioned and not history_seen.is_set())
        except (BotoCoreError, ClientError, CapabilityError):
            if history_seen.is_set():
                raise CapabilityError("storage_history_observed_in_never_versioned_bucket") from None
            raise CapabilityError("storage_probe_cleanup_failed") from None
    return True


def _read(client, bucket, key):
    checkpoint()
    response = client.get_object(Bucket=bucket, Key=key)
    try:
        return response["Body"].read(65)
    finally:
        response["Body"].close()
