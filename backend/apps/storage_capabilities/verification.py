"""Durable history floor and bounded verification cache (model owned by I).

The operations.StorageCapabilityState migration must precede enabling a capability
file. No credentials or endpoint URLs are written to audit metadata.
"""

from datetime import timedelta
from contextvars import ContextVar

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .contracts import CapabilityError

_unbound_migration_probe = ContextVar("unbound_storage_migration_probe", default=False)


def _states():
    try:
        return apps.get_model("operations", "StorageCapabilityState").objects.using("default")
    except LookupError:
        raise CapabilityError("storage_verification_schema_unavailable") from None


def verification_ttl():
    ttl = getattr(settings, "STORAGE_CAPABILITY_TTL_SECONDS", 900)
    if type(ttl) is not int or not 60 <= ttl <= 86400:
        raise CapabilityError("storage_verification_ttl_invalid")
    return ttl


def _check_history(state, contract):
    if state.history_possible and contract.versioning == "never_versioned":
        raise CapabilityError("storage_history_downgrade_requires_new_bucket")
    if contract.generation < state.generation:
        raise CapabilityError("storage_generation_regressed")
    if (
        state.configuration_fingerprint != contract.fingerprint
        and contract.generation == state.generation
    ):
        raise CapabilityError("storage_generation_not_advanced")


def _binding_role(contract):
    if _unbound_migration_probe.get():
        return None
    from .runtime import configured_contracts

    contracts = configured_contracts()
    if not contracts:
        return None  # pre-existing host contract; never clear a saved role binding
    for role, current in contracts.items():
        if current.fingerprint == contract.fingerprint:
            return role
    raise CapabilityError("storage_configuration_changed")


def _check_binding(contract, role):
    if role is None:
        return
    bound = _states().filter(logical_role=role).first()
    if bound is not None and bound.identity_fingerprint != contract.identity.fingerprint:
        raise CapabilityError("storage_bucket_migration_required")
    state = _states().filter(identity_fingerprint=contract.identity.fingerprint).first()
    if state is not None and state.logical_role not in {None, role}:
        raise CapabilityError("storage_bucket_migration_required")


def verified_state(contract):
    role = _binding_role(contract)
    state = _states().filter(identity_fingerprint=contract.identity.fingerprint).first()
    if state is None:
        _check_binding(contract, role)
        raise CapabilityError("storage_capabilities_unverified")
    _check_history(state, contract)
    if role is not None and state.logical_role != role:
        _check_binding(contract, role)
        raise CapabilityError("storage_bucket_binding_unverified")
    if state.configuration_fingerprint != contract.fingerprint:
        raise CapabilityError("storage_configuration_changed")
    if not state.verified_at or state.verified_at <= timezone.now() - timedelta(seconds=verification_ttl()):
        raise CapabilityError("storage_verification_expired")
    return state


def verify_and_save(client, contract, *, probe_prefix="spaceworks-capability-probes/",
                    object_lock_mode=None, object_lock_retention_seconds=60):
    """Explicit startup/setup refresh, outside domain transactions and row locks.

    Probes never create buckets, change versioning, policy, CORS or Object Lock.
    Failed/unknown checks do not refresh the successful cache timestamp.
    """
    from .probes import inspect_bucket, probe_conditional_create
    from .runtime import client_identity
    from .operation_probes import probe_object_operations, probe_object_lock
    from .upload_probes import probe_upload_methods

    if transaction.get_connection().in_atomic_block:
        raise CapabilityError("storage_probe_inside_transaction")
    if client_identity(client, contract.identity.bucket) != contract.identity:
        raise CapabilityError("storage_client_identity_mismatch")
    role = _binding_role(contract)
    _check_binding(contract, role)
    previous = _states().filter(identity_fingerprint=contract.identity.fingerprint).first()
    if previous is not None:
        _check_history(previous, contract)
    started_at = timezone.now()
    try:
        facts = inspect_bucket(client, contract)
        if contract.conditional_create is True:
            facts["conditional_create"] = probe_conditional_create(
                client, bucket=contract.identity.bucket, prefix=probe_prefix,
                never_versioned=contract.versioning == "never_versioned",
            )
        facts.update(probe_object_operations(client, contract))
        facts.update(probe_upload_methods(client, contract))
        if object_lock_mode is not None:
            facts.update(probe_object_lock(client, contract, mode=object_lock_mode,
                                           retention_seconds=object_lock_retention_seconds))
    except Exception as exc:
        code = exc.code if isinstance(exc, CapabilityError) else "storage_probe_unknown"
        _invalidate(contract, started_at, code)
        raise CapabilityError(code) from None
    with transaction.atomic():
        states = _states()
        _check_binding(contract, role)
        try:
            state, created = states.get_or_create(
                identity_fingerprint=contract.identity.fingerprint,
                defaults={
                    "generation": contract.generation, "logical_role": role,
                    "identity": {"endpoint": contract.identity.endpoint,
                                 "region": contract.identity.region, "bucket": contract.identity.bucket},
                    "configuration_fingerprint": contract.fingerprint,
                    "history_possible": contract.versioning != "never_versioned", "facts": {},
                },
            )
        except IntegrityError:
            raise CapabilityError("storage_bucket_migration_required") from None
        state = states.select_for_update().get(pk=state.pk)
        _check_history(state, contract)
        state.generation = contract.generation
        if role is not None:
            state.logical_role = role
        state.configuration_fingerprint = contract.fingerprint
        state.history_possible |= contract.versioning != "never_versioned"
        state.facts = facts
        state.verified_at = timezone.now()
        state.save(update_fields=(
            "generation", "configuration_fingerprint", "history_possible", "facts", "verified_at", "logical_role",
        ))
        from apps.audit import services as audit

        audit.record(None, "storage.capabilities_verified", target=state, meta={
            "identity_fingerprint": contract.identity.fingerprint,
            "configuration_fingerprint": contract.fingerprint,
            "generation": contract.generation, "created": created,
            **{key: value for key, value in facts.items() if key.startswith("lock_probe_")},
        })
    return facts


def _invalidate(contract, started_at, code):
    """A failed refresh cannot leave its old successful proof usable."""
    from apps.audit import services as audit

    with transaction.atomic():
        if code == "storage_history_observed_in_never_versioned_bucket":
            _states().get_or_create(identity_fingerprint=contract.identity.fingerprint, defaults={
                "generation": contract.generation, "configuration_fingerprint": contract.fingerprint,
                "identity": {"endpoint": contract.identity.endpoint,
                             "region": contract.identity.region, "bucket": contract.identity.bucket},
                "history_possible": True, "facts": {"failure_code": code},
            })
        state = _states().select_for_update().filter(
            identity_fingerprint=contract.identity.fingerprint,
            configuration_fingerprint=contract.fingerprint,
        ).first()
        if state is not None and (not state.verified_at or state.verified_at <= started_at):
            state.verified_at = None
            if code == "storage_history_observed_in_never_versioned_bucket":
                state.history_possible = True
            state.save(update_fields=("verified_at", "history_possible"))
        audit.record(None, "storage.capabilities_verification_failed", target=state,
                     target_type="storage_capabilities.verification", meta={
                         "identity_fingerprint": contract.identity.fingerprint,
                         "generation": contract.generation, "failure_code": code,
                     })
