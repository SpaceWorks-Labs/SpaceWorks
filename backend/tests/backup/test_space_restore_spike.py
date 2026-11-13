"""B-0 spike: one space round-trips through its per-space archive with IDENTITY ids.

backup -> (drift) -> purge + materialize in ONE transaction -> objects; proves every
dataset row's pk, the space's slug and public code, QR public codes and object bytes come
back equal, money recorded after the restore point is kept, and another space is untouched.
"""

import uuid

import pytest
from django.db import transaction

from apps.backup.space_restore_apply import apply_space_restore
from apps.backup.space_restore_objects import restore_objects
from apps.boxes.models import QrCode
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import Makerspace
from apps.payments.models import Payment
from tests.backup.space_restore_helpers import (
    build_space_archive, charge, fingerprint, make_user, put_public, read_public, seed_space,
)
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db(transaction=True)


def _columns_that_differ(before, after):
    import json
    left, right = json.loads(before), json.loads(after)
    return {name: (left.get(name), right.get(name)) for name in left if left.get(name) != right.get(name)}


def test_space_round_trips_with_identity_ids_and_other_spaces_untouched(tmp_path):
    with enabled_encryption():
        member = make_user("spike-member")
        space, request = seed_space("spike-source", member)
        other, _other_request = seed_space("spike-other", member)
        kept_before = charge(space, member, "Before the restore point")
        before = fingerprint(space.pk)
        other_before = fingerprint(other.pk)
        slug, public_code = space.slug, space.public_code
        qr_payloads = set(QrCode.objects.filter(makerspace=space).values_list("payload", flat=True))
        archive = build_space_archive(space, tmp_path / "archive")

        # Drift after the restore point.
        HardwareRequest.objects.filter(pk=request.pk).update(status="rejected")
        later = HardwareRequest.objects.create(makerspace=space, requester=member,
                                               requester_username=member.username, requester_name="Later")
        QrCode.objects.filter(makerspace=space).delete()
        Makerspace.objects.filter(pk=space.pk).update(name="Renamed after backup")
        put_public(space.logo_key, b"overwritten after backup")
        kept_after = charge(space, member, "After the restore point")
        from apps.evidence.models import EvidencePhoto
        newer_photo = EvidencePhoto.objects.create(makerspace=space, uploaded_by=member, evidence_type="return",
                                                   object_key="evidence/spike-newer.jpg")

        with transaction.atomic():
            locked = Makerspace.objects.select_for_update().get(pk=space.pk)
            report = apply_space_restore(locked, archive)
        objects = restore_objects(archive, uuid.uuid4())

        space.refresh_from_db()
        assert (space.slug, space.public_code, space.name) == (slug, public_code, "Spike Source")
        assert set(QrCode.objects.filter(makerspace=space).values_list("payload", flat=True)) == qr_payloads
        restored = HardwareRequest.objects.get(pk=request.pk)
        assert restored.requester_name == "Archive Member"  # PII decrypts under the same AAD
        assert restored.requester_contact_email == "member@example.test"
        assert not HardwareRequest.objects.filter(pk=later.pk).exists()
        assert set(Payment.objects.filter(makerspace=space).values_list("pk", flat=True)) == {
            kept_before.pk, kept_after.pk}
        assert read_public(space.logo_key) == b"logo-of-spike-source"
        assert EvidencePhoto.objects.filter(pk=newer_photo.pk).exists()  # kept as an orphaned record
        assert objects["objects_restored"] == 1
        rolled_back = lambda rows: {key: value for key, value in rows.items()  # noqa: E731
                                    if key[0] not in {"payments.Payment", "audit.AuditLog", "evidence.EvidencePhoto"}}
        after, expected = rolled_back(fingerprint(space.pk)), rolled_back(before)
        assert set(after) == set(expected)
        drift = {key: _columns_that_differ(expected[key], after[key]) for key in expected if after[key] != expected[key]}
        assert drift == {}
        assert fingerprint(other.pk) == other_before
        assert report["removed"]["hardware_requests.HardwareRequest"] == 1
