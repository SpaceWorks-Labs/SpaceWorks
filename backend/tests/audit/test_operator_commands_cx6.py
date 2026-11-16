"""Operator command argument boundaries and idempotent provisioning use real keys."""
from io import StringIO
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from apps.audit.batches import activate_scope
from apps.audit.keys import attested_from_id, audit_mac_key_cache, get_audit_mac_key, provision_audit_mac_key
from apps.audit.models import AuditMacKey, AuditSigningKey, AuditSigningKeyRotation
from apps.audit.rotations import scope_head
from apps.makerspaces.models import Makerspace
from tests.accounts.ua1_helpers import platform
from tests.audit_batch_helpers import MemoryAnchorSink

pytestmark = pytest.mark.django_db


def test_provision_deduplicates_explicit_scope_ids_and_is_idempotent():
    first = Makerspace.objects.create(name="Provision one", slug="cx6-provision-one")
    with override_settings(AUDIT_MAC_MASTER_KEY=""):
        second = Makerspace.objects.create(name="Provision two", slug="cx6-provision-two")
    assert AuditMacKey.objects.filter(makerspace=second).count() == 0
    assert set(AuditMacKey.objects.values_list("makerspace_id", flat=True)) == {None, first.pk}
    existing = list(AuditMacKey.objects.order_by("pk").values_list(
        "makerspace_id", "wrapped_key", "attested_from_id", "attested_from_mac"))
    output = StringIO()
    call_command("provision_audit_mac_keys", "--makerspace-id", str(second.pk),
        "--makerspace-id", str(first.pk), "--makerspace-id", str(second.pk), stdout=output, no_color=True)
    assert output.getvalue().splitlines() == [f"scope={first.pk} already provisioned",
        f"scope={second.pk} created", "Audit MAC key provisioning complete: 1 created, 1 existing."]
    assert set(AuditMacKey.objects.values_list("makerspace_id", flat=True)) == {None, first.pk, second.pk}
    assert list(AuditMacKey.objects.exclude(makerspace=second).order_by("pk").values_list(
        "makerspace_id", "wrapped_key", "attested_from_id", "attested_from_mac")) == existing
    before = list(AuditMacKey.objects.order_by("pk").values_list(
        "makerspace_id", "wrapped_key", "attested_from_id", "attested_from_mac"))
    audit_mac_key_cache.clear()
    with CaptureQueriesContext(connection) as queries:
        key = get_audit_mac_key(second.pk)
    assert len(key) == 32
    assert [query["sql"].split()[0] for query in queries] == ["SELECT"]
    assert attested_from_id(second.pk) == 0
    output = StringIO()
    call_command("provision_audit_mac_keys", "--makerspace-id", str(second.pk),
        "--makerspace-id", str(first.pk), "--makerspace-id", str(second.pk), stdout=output, no_color=True)
    assert output.getvalue().splitlines() == [f"scope={first.pk} already provisioned",
        f"scope={second.pk} already provisioned", "Audit MAC key provisioning complete: 0 created, 2 existing."]
    assert list(AuditMacKey.objects.order_by("pk").values_list(
        "makerspace_id", "wrapped_key", "attested_from_id", "attested_from_mac")) == before
    audit_mac_key_cache.clear()
    assert get_audit_mac_key(second.pk) == key


def test_provision_refuses_every_unknown_scope_before_writing_any_key():
    space = Makerspace.objects.create(name="Provision known", slug="cx6-provision-known")
    before = AuditMacKey.objects.count()
    with pytest.raises(CommandError) as error:
        call_command("provision_audit_mac_keys", "--makerspace-id", str(space.pk),
                     "--makerspace-id", "987654321", stdout=StringIO())
    assert str(error.value) == "Unknown makerspace IDs: 987654321"
    assert AuditMacKey.objects.count() == before


def test_global_and_all_provisioning_keep_existing_keys():
    provision_audit_mac_key(None)
    space = Makerspace.objects.create(name="Provision all", slug="cx6-provision-all")
    provision_audit_mac_key(space.pk)
    with override_settings(AUDIT_MAC_MASTER_KEY=""):
        missing = Makerspace.objects.create(name="Provision missing", slug="cx6-provision-missing")
    assert AuditMacKey.objects.filter(makerspace=missing).count() == 0
    output = StringIO()
    call_command("provision_audit_mac_keys", "--global", stdout=output, no_color=True)
    assert output.getvalue().splitlines() == ["scope=global already provisioned",
                                             "Audit MAC key provisioning complete: 0 created, 1 existing."]
    before = list(AuditMacKey.objects.order_by("pk").values_list(
        "makerspace_id", "wrapped_key", "attested_from_id", "attested_from_mac"))
    output = StringIO()
    call_command("provision_audit_mac_keys", "--all", stdout=output, no_color=True)
    assert output.getvalue().splitlines() == ["scope=global already provisioned",
        f"scope={space.pk} already provisioned", f"scope={missing.pk} created",
        "Audit MAC key provisioning complete: 1 created, 2 existing."]
    assert set(AuditMacKey.objects.values_list("makerspace_id", flat=True)) == {None, space.pk, missing.pk}
    assert list(AuditMacKey.objects.exclude(makerspace=missing).order_by("pk").values_list(
        "makerspace_id", "wrapped_key", "attested_from_id", "attested_from_mac")) == before
    audit_mac_key_cache.clear()
    key = get_audit_mac_key(missing.pk)
    assert len(key) == 32
    after = list(AuditMacKey.objects.order_by("pk").values_list(
        "makerspace_id", "wrapped_key", "attested_from_id", "attested_from_mac"))
    output = StringIO()
    call_command("provision_audit_mac_keys", "--all", stdout=output, no_color=True)
    assert output.getvalue().splitlines() == ["scope=global already provisioned",
        f"scope={space.pk} already provisioned", f"scope={missing.pk} already provisioned",
        "Audit MAC key provisioning complete: 0 created, 3 existing."]
    assert list(AuditMacKey.objects.order_by("pk").values_list(
        "makerspace_id", "wrapped_key", "attested_from_id", "attested_from_mac")) == after
    audit_mac_key_cache.clear()
    assert get_audit_mac_key(missing.pk) == key


@pytest.mark.parametrize("identifier,message", [(0, "--makerspace-id must be a positive integer."),
    (-1, "--makerspace-id must be a positive integer."), (987654321, "The makerspace does not exist.")])
def test_rotation_refuses_invalid_scopes(identifier, message):
    root = platform("cx6-rotation-scope-root")
    with pytest.raises(CommandError) as error:
        call_command("rotate_audit_signing_key", "--makerspace-id", str(identifier),
                     "--actor-user-id", str(root.pk), "--dry-run", stdout=StringIO())
    assert str(error.value) == message
    assert AuditSigningKeyRotation.objects.count() == 0


@pytest.fixture
def signing_scope(settings):
    settings.AUDIT_ATTESTATION_DEPLOYMENT_ID = "cx6-command-deployment"
    space = Makerspace.objects.create(name="Signing scope", slug="cx6-signing-scope")
    root = platform("cx6-signing-root")
    key = activate_scope(space.pk, MemoryAnchorSink())
    return space, root, key


def test_dry_run_reports_only_public_scope_facts_without_creating_a_rotation(signing_scope):
    space, root, key = signing_scope
    output = StringIO()
    call_command("rotate_audit_signing_key", "--makerspace-id", str(space.pk), "--actor-user-id", str(root.pk),
                 "--dry-run", stdout=output)
    seq, digest = scope_head(space.pk)
    assert json.loads(output.getvalue()) == {"scope": space.pk, "current_fingerprint": key.fingerprint,
        "current_version": key.version, "head_seq": seq, "head_root": digest.hex(), "pending_rotation_id": None}
    assert AuditSigningKeyRotation.objects.count() == 0
    assert AuditSigningKey.objects.filter(makerspace=space, is_active=True).count() == 1


@pytest.mark.parametrize("field,value,message", [
    ("expected_current_fingerprint", "x", "--expected-current-fingerprint must be 64 hex characters."),
    ("expected_head_seq", -1, "--expected-head-seq must be zero or greater."),
    ("expected_head_root", "z" * 64, "--expected-head-root must be 64 hex characters."),
])
def test_execute_refuses_invalid_expectations_before_preparing_any_rotation(signing_scope, field, value, message):
    space, root, key = signing_scope
    seq, digest = scope_head(space.pk)
    kwargs = {"expected_current_fingerprint": key.fingerprint, "expected_head_seq": seq,
              "expected_head_root": digest.hex(), field: value}
    with pytest.raises(CommandError) as error:
        call_command("rotate_audit_signing_key", "--makerspace-id", str(space.pk),
            "--actor-user-id", str(root.pk), "--execute", stdout=StringIO(), **kwargs)
    assert str(error.value) == message
    assert AuditSigningKeyRotation.objects.count() == 0
    key.refresh_from_db()
    assert key.pending_rotation_id is None


def test_abort_without_pending_rotation_is_an_exact_refusal(signing_scope):
    space, root, _ = signing_scope
    with pytest.raises(CommandError) as error:
        call_command("rotate_audit_signing_key", "--makerspace-id", str(space.pk),
                     "--actor-user-id", str(root.pk), "--abort-pending", stdout=StringIO())
    assert str(error.value) == "The scope has no pending audit signing-key rotation."
    assert AuditSigningKeyRotation.objects.count() == 0
