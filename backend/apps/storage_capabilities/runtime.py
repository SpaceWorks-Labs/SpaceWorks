"""Resolve each client/bucket against the saved, recently verified contract."""

from django.conf import settings

from .configuration import read_configuration
from .contracts import CapabilityError, StorageIdentity


def configured_contracts():
    path = getattr(settings, "STORAGE_CAPABILITIES_FILE", "")
    if not path and (
        getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") == "managed"
        or getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"
    ):
        raise CapabilityError("storage_capability_file_required")
    return read_configuration(path) if path else {}


def client_identity(client, bucket):
    return StorageIdentity.build(
        client.meta.endpoint_url, client.meta.region_name, bucket,
    )


def capabilities_for(client, bucket, *, required=False, role=None):
    contracts = configured_contracts()
    if not contracts:
        # Existing full-server configuration: retain its explicit presign setting.
        # Unknown history still requires strict version enumeration in deletion.
        return None
    identity = client_identity(client, bucket)
    if role is not None:
        expected = contracts.get(role)
        if expected is None or expected.identity != identity:
            raise CapabilityError("storage_bucket_role_mismatch")
    matches = [item for item in contracts.values() if item.identity == identity]
    if not matches:
        if required:
            raise CapabilityError("storage_client_identity_mismatch")
        return None  # independent offsite clients must use strict history handling
    from .verification import verified_state

    contract = matches[0]
    verified_state(contract)
    return contract


def require_capability(client, bucket, name, *, role=None):
    if name not in {"conditional_create", "copy", "multipart", "object_lock", "cors_management"}:
        raise CapabilityError("storage_feature_invalid")
    contract = capabilities_for(client, bucket, required=True, role=role)
    if contract is not None:
        if getattr(contract, name) is not True:
            raise CapabilityError(f"storage_{name}_unavailable")
        from .verification import verified_state

        if verified_state(contract).facts.get(name) is not True:
            raise CapabilityError(f"storage_{name}_unproven")
    return contract


def require_object_lock(client, bucket, *, mode, retention_days):
    """Anchor sinks must prove their actual selected mode and retention window."""
    if mode not in {"COMPLIANCE", "GOVERNANCE"} or type(retention_days) is not int or retention_days < 1:
        raise CapabilityError("storage_object_lock_policy_invalid")
    contract = require_capability(client, bucket, "object_lock")
    if contract is not None:
        from .verification import verified_state

        facts = verified_state(contract).facts
        if (facts.get("lock_probe_mode") != mode
            or facts.get("lock_probe_retention_seconds", 0) < retention_days * 86400):
            raise CapabilityError("storage_object_lock_policy_unproven")
    return contract
