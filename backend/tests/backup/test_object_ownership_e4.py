import hashlib

import pytest

from django.utils import timezone

from apps.audit.models import AuditLog
from apps.backup.models import BackupArchive, RestoreOperation, RestoreRollbackObject
from apps.backup.object_ownership import (
    MAIN_COMPONENT,
    ObjectOwnershipPlan,
    ObjectReference,
    build_object_ownership_plan,
)
from apps.backup.object_ownership_registry import ReferencePolicy
from apps.backup.build_errors import BackupBuildError
from apps.events.models import Event, EventRegistration
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace


pytestmark = pytest.mark.django_db(transaction=True)


def _reference(key, *, owner=MAIN_COMPONENT, policy=""):
    return ObjectReference(
        bucket_kind="private",
        object_key=key,
        site=f"test.Model:1:object_key:{key}",
        candidate_owner=owner,
        canonical_makerspace_id=None,
        module_key="",
        coordination_policy=policy,
        coordination_makerspace_id=None,
    )


def _manifest(root, key, *, size=None, digest=None, owner=MAIN_COMPONENT):
    payload = (root / "private" / key).read_bytes()
    return [{
        "bucket_kind": "private",
        "key": key,
        "canonical_component": owner,
        "size": len(payload) if size is None else size,
        "sha256": hashlib.sha256(payload).hexdigest() if digest is None else digest,
    }]


def test_one_platform_component_owns_a_byte_two_spaces_share():
    sovereign = Makerspace.objects.create(
        name="E4 shared sovereign",
        slug="e4-shared-sovereign",
    )
    ordinary = Makerspace.objects.create(
        name="E4 shared ordinary", slug="e4-shared-ordinary"
    )
    for space, name in ((sovereign, "Sliced"), (ordinary, "Main")):
        InventoryProduct.objects.create(
            makerspace=space, name=name, image_key="e4/shared-byte.png"
        )

    plan = build_object_ownership_plan()
    assert "e4/shared-byte.png" in plan.closure(MAIN_COMPONENT)["public_image"]


def test_copy_key_bucket_is_resolved_from_each_row():
    space = Makerspace.objects.create(name="E4 rollback", slug="e4-rollback")
    archive = BackupArchive.objects.create(
        scope=BackupArchive.Scope.DEPLOYMENT,
        object_key="backup-archives/deployment/e4-source.tar.age",
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )
    restore = RestoreOperation.objects.create(
        archive=archive, kind=RestoreOperation.Kind.ROLLBACK_IN_PLACE
    )
    row = RestoreRollbackObject.objects.create(
        restore=restore,
        makerspace=space,
        bucket_kind=RestoreRollbackObject.BucketKind.PRIVATE,
        source_key="source-key",
        copy_key="rollback/e4/copy",
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    private_plan = build_object_ownership_plan()
    assert ("private", row.copy_key) in private_plan.multimap
    assert ("public_image", row.copy_key) not in private_plan.multimap

    RestoreRollbackObject.objects.filter(pk=row.pk).update(
        bucket_kind=RestoreRollbackObject.BucketKind.PUBLIC_IMAGE
    )
    public_plan = build_object_ownership_plan()
    assert ("public_image", row.copy_key) in public_plan.multimap
    assert ("private", row.copy_key) not in public_plan.multimap


def test_unknown_audit_object_variant_refuses_instead_of_json_guessing():
    space = Makerspace.objects.create(name="E4 audit", slug="e4-audit")
    AuditLog.objects.create(
        makerspace=space,
        action="future.object_variant",
        meta={"object_key": "future/unknown.bin"},
    )

    with pytest.raises(BackupBuildError, match="undeclared object-reference variant"):
        build_object_ownership_plan()


@pytest.mark.parametrize(
    ("size", "digest"),
    ((999, None), (None, "0" * 64)),
)
def test_packaged_byte_must_match_immutable_size_and_digest(
    tmp_path, size, digest
):
    key = "captured.bin"
    path = tmp_path / "private" / key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"immutable E4 bytes")
    plan = ObjectOwnershipPlan((_reference(key),))

    with pytest.raises(BackupBuildError, match="immutable capture ledger"):
        plan.bind_component(
            MAIN_COMPONENT,
            tmp_path,
            _manifest(tmp_path, key, size=size, digest=digest),
        )


def test_manifest_object_requires_reference_or_exact_coordination_policy(tmp_path):
    key = "coordination.bin"
    path = tmp_path / "private" / key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"coordination bytes")

    with pytest.raises(BackupBuildError, match="manifest closure differ"):
        ObjectOwnershipPlan(()).bind_component(
            MAIN_COMPONENT, tmp_path, _manifest(tmp_path, key)
        )

    allowed = ObjectOwnershipPlan((
        _reference(
            key,
            owner=None,
            policy=ReferencePolicy.PACKAGE_MAIN_COORDINATION,
        ),
    ))
    allowed.bind_component(
        MAIN_COMPONENT, tmp_path, _manifest(tmp_path, key)
    )
    allowed.assert_complete()


def test_manifest_cannot_change_after_capture(tmp_path):
    key = "bound.bin"
    path = tmp_path / "private" / key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"bound bytes")
    plan = ObjectOwnershipPlan((_reference(key),))
    manifest = _manifest(tmp_path, key)
    plan.bind_component(MAIN_COMPONENT, tmp_path, manifest)
    manifest[0]["sha256"] = "f" * 64

    with pytest.raises(BackupBuildError, match="immutable capture ledger"):
        plan.verify_component(MAIN_COMPONENT, manifest)


def test_abandoned_upload_receipt_key_is_coordination_only_never_archive_content():
    from apps.backup.archive_objects import NON_OBJECT_KEY_FIELDS, object_closure
    from apps.backup.object_ownership_registry import FIELD_OBJECT_RULES

    rule = next(
        item for item in FIELD_OBJECT_RULES
        if item.model_label == "evidence.EvidenceAbandonedUploadReceipt"
    )
    assert (rule.field_name, rule.policy) == ("object_key", ReferencePolicy.COORDINATION_ONLY)
    assert ("evidence.EvidenceAbandonedUploadReceipt", "object_key") not in NON_OBJECT_KEY_FIELDS
    assert all("receipt" not in key for key in object_closure()["private"])
