"""Shared capability-aware deletion, preserving the existing import surface."""

from apps.storage_capabilities import CapabilityError, capabilities_for
from apps.storage_capabilities.deletion import (
    DeletionEvidence, assert_exact_absent, delete_exact_key, delete_owned_prefix,
)

# Kept for consumers importing the historical constant. It is never a fallback.
UNSUPPORTED_LIST_OBJECT_VERSIONS_ERROR_CODES = frozenset({
    "InvalidRequest", "MethodNotAllowed", "NotImplemented", "UnsupportedOperation",
    "XNotImplemented",
})


def deletion_contract(client, bucket):
    contract = capabilities_for(client, bucket)
    if contract is not None and contract.versioning == "never_versioned":
        return True
    if contract is not None and contract.list_delete_versions is not True:
        raise CapabilityError("storage_history_listing_required")
    return False


def delete_all_versions(client, *, bucket, key, require_version_listing=False):
    """Confirm absence before callers free quota or mark expiry terminal.

    ``require_version_listing`` remains accepted for old callers. The verified
    never-versioned contract is equivalent proof of no history; every other
    bucket always requires enumeration, including suspended/unknown buckets.
    """
    return delete_exact_key(
        client, bucket=bucket, key=key,
        never_versioned=deletion_contract(client, bucket),
    )


__all__ = [
    "CapabilityError", "DeletionEvidence", "assert_exact_absent", "delete_all_versions",
    "delete_owned_prefix", "deletion_contract",
]
