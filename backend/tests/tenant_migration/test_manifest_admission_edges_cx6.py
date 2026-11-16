"""Admission/manifest boundaries without a dump, restore or migration rewind."""
from copy import deepcopy
import hashlib
import json

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.admission import closure_digest, revoke_approval, validate_snapshot_approval
from apps.tenant_migration.models_protocol import DisclosureClosureApproval
from apps.tenant_migration.protocol_errors import ClosureAdmissionError, ClosureChangedError
from apps.tenant_migration.tenant_dump_errors import TenantDumpVerificationError
from apps.tenant_migration.tenant_dump_outer_manifest_facts import encrypted_member_fact, source_build_fact
from apps.tenant_migration.tenant_dump_outer_manifest_validation import validate_outer_manifest
from tests.accounts.ua1_helpers import person, platform


def manifest():
    return {"format": "spaceworks-tenant-dump-v1", "version": 1, "artifact_id": "artifact",
        "capture_id": "capture", "outer_recipient_fingerprints": ["a", "b"],
        "tenant_dek_recipient_fingerprints": ["c"],
        "encrypted_members": [{"path": "payload.age", "size": 1, "sha256": "a" * 64}],
        "source_build": {"source_hash": "build"}, "postgres_major": 16, "compatibility": {}}


@pytest.mark.parametrize("path,bad", [
    (("format",), "another-format"), (("version",), 2), (("artifact_id",), ""), (("capture_id",), None),
    (("outer_recipient_fingerprints",), []), (("outer_recipient_fingerprints",), ["b", "a"]),
    (("outer_recipient_fingerprints",), ["a", "a"]), (("tenant_dek_recipient_fingerprints",), [""]),
    (("encrypted_members",), []), (("encrypted_members",), [None]),
    (("encrypted_members", 0, "size"), True), (("encrypted_members", 0, "size"), 0),
    (("encrypted_members", 0, "size"), -1), (("encrypted_members", 0, "path"), "../payload.age"),
    (("encrypted_members", 0, "sha256"), "A" * 64), (("encrypted_members", 0, "sha256"), "g" * 64),
    (("source_build",), {}), (("source_build", "source_hash"), ""), (("source_build", "source_hash"), 12),
    (("postgres_major",), True), (("postgres_major",), 9), (("postgres_major",), 100),
    (("compatibility",), []), (("compatibility",), {"catalog_sha256": "a" * 64}),
])
def test_outer_manifest_rejects_each_invalid_nested_fact(path, bad):
    value = manifest()
    cursor = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = bad
    with pytest.raises(TenantDumpVerificationError) as error:
        validate_outer_manifest(value)
    assert str(error.value) == "The Lane D outer manifest structure is invalid."


@pytest.mark.parametrize("extra", ["rows", "users", "encryption_key"])
def test_public_manifest_does_not_accept_additional_disclosing_fields(extra):
    value = manifest()
    value[extra] = "private"
    with pytest.raises(TenantDumpVerificationError) as error:
        validate_outer_manifest(value)
    assert str(error.value) == "The Lane D outer manifest structure is invalid."


def compatibility():
    return {"catalog_sha256": "a" * 64, "content_ledger_count": 0, "content_ledger_sha256": "b" * 64,
            "derivation_policy_sha256": "c" * 64, "source_pii_mode": "encrypted"}


@pytest.mark.parametrize("key,bad", [("catalog_sha256", "x"), ("content_ledger_sha256", None),
    ("derivation_policy_sha256", "D" * 64), ("content_ledger_count", True),
    ("content_ledger_count", -1), ("source_pii_mode", "unknown")])
def test_compatibility_facts_are_closed_and_typed(key, bad):
    value = manifest()
    value["compatibility"] = compatibility()
    assert validate_outer_manifest(value) is True
    value["compatibility"][key] = bad
    with pytest.raises(TenantDumpVerificationError) as error:
        validate_outer_manifest(value)
    assert str(error.value) == "The Lane D outer manifest structure is invalid."


@pytest.mark.parametrize("major", [10, 16, 99])
def test_manifest_valid_boundaries(major):
    value = manifest()
    value["postgres_major"] = major
    assert validate_outer_manifest(value) is True


@pytest.mark.parametrize("body", [b"not-json", b"\xff", b"{}", b"null", b'{"source_hash": 7}', b'{"source_hash": ""}'])
def test_unreadable_build_metadata_uses_non_disclosing_unknown(tmp_path, body):
    path = tmp_path / "build.json"
    path.write_bytes(body)
    assert source_build_fact(path) == {"source_hash": "unknown"}
    assert source_build_fact(tmp_path / "missing") == {"source_hash": "unknown"}


def test_encrypted_member_facts_come_from_actual_bytes_and_never_reveal_local_path(tmp_path):
    path = tmp_path / "private-local-name.age"
    path.write_bytes(b"encrypted payload")
    assert encrypted_member_fact(path) == {"path": "payload.age", "sha256": hashlib.sha256(b"encrypted payload").hexdigest(),
                                          "size": len(b"encrypted payload")}
    build = tmp_path / "build.json"
    build.write_text(json.dumps({"source_hash": "abcdef", "private": "ignored"}), encoding="utf-8")
    assert source_build_fact(build) == {"source_hash": "abcdef"}


@pytest.mark.parametrize("mutation", ["revoked", "digest", "identities", "approvals"])
def test_snapshot_approval_rejects_each_post_review_change(mutation):
    identities = [{"id": 1, "display_name": "Maker"}, {"id": 2, "display_name": "صانع"}]
    approval = DisclosureClosureApproval(closure_digest=closure_digest(identities), identity_ids=["1", "2"],
                                        approved_identity_ids=["1"])
    assert validate_snapshot_approval(approval, identities) == {1}
    if mutation == "revoked":
        approval.revoked_at = timezone.now()
    elif mutation == "digest":
        identities = deepcopy(identities)
        identities[1]["display_name"] = "Changed"
    elif mutation == "identities":
        approval.identity_ids = ["2", "1"]
    else:
        approval.approved_identity_ids = ["3"]
    with pytest.raises(ClosureChangedError) as error:
        validate_snapshot_approval(approval, identities)
    assert error.value.code == "closure_changed"
    assert str(error.value) == "The disclosure closure changed after approval; the export was refused."


@pytest.mark.django_db
def test_only_superadmin_can_revoke_and_replay_preserves_the_first_audit():
    space = Makerspace.objects.create(name="Closure", slug="cx6-closure")
    root, member = platform("cx6-closure-root"), person("cx6-closure-member")
    approval = DisclosureClosureApproval.objects.create(makerspace=space, approved_by=root,
        closure_digest=closure_digest([]), identity_ids=[], approved_identity_ids=[])
    with pytest.raises(ClosureAdmissionError) as error:
        revoke_approval(actor=member, approval=approval)
    assert error.value.code == "closure_admission_failed"
    assert str(error.value) == "Only a source superadmin may approve disclosure."
    approval.refresh_from_db()
    assert approval.revoked_at is None
    first = revoke_approval(actor=root, approval=approval)
    second = revoke_approval(actor=root, approval=approval)
    assert first.revoked_at == second.revoked_at
    assert second.revoked_by_id == root.pk
    assert AuditLog.objects.filter(action="tenant_migration.disclosure_revoked", target_id=str(approval.pk)).count() == 1
