"""One-page byte observations for resumable free-profile reconciliation.

These are observations, not quota mutations or an atomic bucket snapshot. I owns
the durable run/cursor/delta ledger and must publish totals only after completion
plus replay of concurrent finalized/deleted deltas. Interrupted/stale/unknown
inventory must remain unknown rather than displaying a false zero.
"""

from dataclasses import dataclass

from botocore.exceptions import BotoCoreError, ClientError

from .budget import checkpoint
from .contracts import CapabilityError
from .runtime import capabilities_for, client_identity


@dataclass(frozen=True)
class UsagePage:
    identity_fingerprint: str
    configuration_fingerprint: str
    generation: int
    bytes_observed: int
    objects_observed: int
    delete_markers_observed: int
    continuation: dict | None
    coverage: str
    includes_incomplete_uploads: bool = False


def usage_page(client, *, bucket, cursor=None, page_size=100):
    """At most one LIST request, bounded memory, identity-bound continuation."""
    if type(page_size) is not int or not 1 <= page_size <= 1000:
        raise CapabilityError("storage_usage_page_size_invalid")
    contract = capabilities_for(client, bucket, required=True)
    if contract is None:
        raise CapabilityError("storage_usage_requires_capability_contract")
    identity = client_identity(client, bucket).fingerprint
    cursor = _cursor(cursor, identity, contract.fingerprint)
    params = {"Bucket": bucket, "MaxKeys": page_size}
    checkpoint()
    try:
        if contract.versioning == "never_versioned":
            if cursor and cursor.get("token"):
                params["ContinuationToken"] = cursor["token"]
            page = client.list_objects_v2(**params)
            objects = page.get("Contents", ())
            markers = ()
            next_cursor = {"token": page.get("NextContinuationToken")}
            coverage = "current_objects"
        else:
            if contract.list_delete_versions is not True:
                raise CapabilityError("storage_history_listing_required")
            if cursor:
                params.update({name: cursor[name] for name in ("KeyMarker", "VersionIdMarker") if name in cursor})
            page = client.list_object_versions(**params)
            objects = page.get("Versions", ())
            markers = page.get("DeleteMarkers", ())
            next_cursor = {"KeyMarker": page.get("NextKeyMarker"),
                           "VersionIdMarker": page.get("NextVersionIdMarker")}
            coverage = "retained_versions"
    except CapabilityError:
        raise
    except (BotoCoreError, ClientError):
        raise CapabilityError("storage_usage_unknown") from None
    continuation = None
    if page.get("IsTruncated"):
        next_cursor = {key: value for key, value in next_cursor.items() if value is not None}
        required = "token" if contract.versioning == "never_versioned" else "KeyMarker"
        if not next_cursor.get(required) or next_cursor == {k: v for k, v in cursor.items() if k not in {"identity", "configuration"}}:
            raise CapabilityError("storage_usage_pagination_invalid")
        continuation = {"identity": identity, "configuration": contract.fingerprint, **next_cursor}
    sizes = [item.get("Size") for item in objects]
    if any(type(size) is not int or size < 0 for size in sizes):
        raise CapabilityError("storage_usage_response_invalid")
    return UsagePage(identity, contract.fingerprint, contract.generation, sum(sizes),
                     len(objects), len(markers), continuation, coverage)


def _cursor(cursor, identity, configuration):
    if cursor is None:
        return {}
    if (
        not isinstance(cursor, dict) or cursor.get("identity") != identity
        or cursor.get("configuration") != configuration
        or set(cursor) - {"identity", "configuration", "token", "KeyMarker", "VersionIdMarker"}
        or any(not isinstance(value, str) or len(value) > 8192 for value in cursor.values())
    ):
        raise CapabilityError("storage_usage_cursor_invalid")
    return cursor
