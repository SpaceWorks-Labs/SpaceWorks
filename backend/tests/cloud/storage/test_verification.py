from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.storage_capabilities import verification
from apps.storage_capabilities.contracts import CapabilityError
from tests.cloud.storage.test_contracts import contract


def state(value, **changes):
    return SimpleNamespace(**{
        "history_possible": value.versioning != "never_versioned",
        "generation": value.generation, "configuration_fingerprint": value.fingerprint,
        "verified_at": timezone.now(), "facts": {"conditional_create": True}, **changes,
    })


def test_json_edit_cannot_downgrade_previously_versioned_bucket():
    old = contract(versioning="enabled", list_delete_versions=True)
    with pytest.raises(CapabilityError, match="requires_new_bucket"):
        verification._check_history(state(old), contract(generation=2))


def test_same_generation_change_and_generation_rollback_refuse():
    old = contract()
    with pytest.raises(CapabilityError, match="not_advanced"):
        verification._check_history(state(old), contract(copy=False))
    with pytest.raises(CapabilityError, match="regressed"):
        verification._check_history(state(contract(generation=2)), old)


def test_expired_or_missing_proof_is_not_ready(monkeypatch, settings):
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.STORAGE_CAPABILITY_TTL_SECONDS = 900
    states = Mock()
    monkeypatch.setattr(verification, "_states", lambda: states)
    states.filter.return_value.first.return_value = None
    with pytest.raises(CapabilityError, match="unverified"):
        verification.verified_state(contract())
    states.filter.return_value.first.return_value = state(contract(), verified_at=timezone.now() - timedelta(seconds=901))
    with pytest.raises(CapabilityError, match="expired"):
        verification.verified_state(contract())


def test_replacing_a_bound_bucket_requires_a_verified_migration(monkeypatch):
    states = Mock()
    states.filter.return_value.first.return_value = SimpleNamespace(identity_fingerprint="previous-versioned-bucket")
    monkeypatch.setattr(verification, "_states", lambda: states)
    with pytest.raises(CapabilityError, match="bucket_migration_required"):
        verification._check_binding(contract(), "private")


@pytest.mark.parametrize("interval", [600, 1800])
def test_free_two_binding_refresh_keeps_proofs_live_across_cycles(settings, monkeypatch, interval):
    from contextlib import nullcontext
    from dataclasses import replace
    import time
    from apps.operations import storage_qualification
    from apps.operations.cloud_jobs.contracts import ChunkContext
    from apps.storage_capabilities.contracts import StorageIdentity
    from cloud_contracts.deployment import DeploymentSelection
    from config.cloud_settings.configuration import storage_proof_ttl

    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    # Exercise the production default derived from a real two-binding descriptor.
    class Env:
        def __call__(self, name, default=None):
            return default
        def int(self, name, default=None):
            return interval if name == "FREE_TICK_INTERVAL_SECONDS" else default

    settings.STORAGE_CAPABILITY_TTL_SECONDS = storage_proof_ttl(Env(), DeploymentSelection("managed", "free"))
    contracts = {"private": contract(), "public_image": replace(contract(),
        identity=StorageIdentity.build("https://s3.example.test", "auto", "public-images"))}
    now = timezone.now()
    records = {item.identity.fingerprint: state(item, verified_at=now) for item in contracts.values()}
    clock = [now]
    monkeypatch.setattr(verification.timezone, "now", lambda: clock[0])
    states = Mock()
    states.filter.side_effect = lambda **kwargs: SimpleNamespace(first=lambda: records[kwargs["identity_fingerprint"]])
    monkeypatch.setattr(verification, "_states", lambda: states)
    monkeypatch.setattr(verification, "_binding_role", lambda value: None)
    monkeypatch.setattr("apps.storage_capabilities.runtime.configured_contracts", lambda: contracts)
    monkeypatch.setattr("apps.operations.cloud_runtime.writer", lambda *args: nullcontext())

    def refresh(**kwargs):
        for role in kwargs["roles"]:
            records[contracts[role].identity.fingerprint].verified_at = clock[0]

    monkeypatch.setattr(storage_qualification, "verify_bindings", refresh)
    checkpoint = {}
    for tick in range(1, 9):
        clock[0] = now + timedelta(seconds=tick * interval)
        # Both proofs must still be usable immediately before the next refresh.
        for item in contracts.values():
            verification.verified_state(item)
        context = ChunkContext(time.monotonic() + 20, lambda: None, checkpoint, None, 1)
        checkpoint = storage_qualification.refresh_chunk(context).checkpoint
    clock[0] += timedelta(seconds=settings.STORAGE_CAPABILITY_TTL_SECONDS + 1)
    with pytest.raises(CapabilityError, match="expired"):
        verification.verified_state(contracts["private"])


def test_free_proof_default_counts_optional_bindings(settings, monkeypatch):
    from cloud_contracts.deployment import DeploymentSelection
    from config.cloud_settings.configuration import storage_proof_ttl
    from django.core.exceptions import ImproperlyConfigured
    monkeypatch.setattr("apps.storage_capabilities.configuration.read_configuration", lambda path: {
        "private": None, "public_image": None, "anchor": None, "offsite_archive": None,
    })

    class Env:
        ttl = None
        def __call__(self, name, default=None):
            return "/private/storage.json" if name == "STORAGE_CAPABILITIES_FILE" else default
        def int(self, name, default=None):
            return self.ttl if name == "STORAGE_CAPABILITY_TTL_SECONDS" and self.ttl is not None else default

    env = Env()
    assert storage_proof_ttl(env, DeploymentSelection("managed", "free")) == 3020
    env.ttl = 1820
    with pytest.raises(ImproperlyConfigured):
        storage_proof_ttl(env, DeploymentSelection("managed", "free"))


@pytest.mark.django_db(transaction=True)
def test_durable_verification_records_history_and_audit(settings, monkeypatch):
    """Requires I's operations.StorageCapabilityState migration in the combined tree."""
    from django.apps import apps
    from apps.audit.models import AuditLog
    from apps.storage_capabilities import probes, operation_probes, upload_probes

    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.STORAGE_CAPABILITIES_FILE = ""

    value = contract(versioning="enabled", list_delete_versions=True, conditional_create=False)
    monkeypatch.setattr(probes, "inspect_bucket", lambda *args: {"versioning": "enabled"})
    monkeypatch.setattr(operation_probes, "probe_object_operations", lambda *args: {})
    monkeypatch.setattr(upload_probes, "probe_upload_methods", lambda *args: {"presign_methods": ["put"]})
    s3 = Mock(meta=SimpleNamespace(endpoint_url=value.identity.endpoint, region_name=value.identity.region))
    verification.verify_and_save(s3, value)
    record = apps.get_model("operations", "StorageCapabilityState").objects.get(identity_fingerprint=value.identity.fingerprint)
    assert record.history_possible
    assert AuditLog.objects.filter(action="storage.capabilities_verified").exists()
    with pytest.raises(CapabilityError, match="requires_new_bucket"):
        verification.verify_and_save(s3, contract(generation=2))
