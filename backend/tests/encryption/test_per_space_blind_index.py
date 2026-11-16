"""Per-space search key (#120): derived per space, rotated with a re-index, search never blinks."""

import pytest
from django.core.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.encryption.blind_index import exact_hash, search_key
from apps.encryption.models import MakerspaceSearchKey, PiiBlindIndex
from apps.encryption.rotation import start_search_key_rotation
from apps.encryption.search import indexed_candidates
from apps.encryption.search_keys import derive, search_keys, write_key
from tests.encryption.conftest import enabled_encryption
from tests.encryption.test_key_rotation import _run_to_completion, _space_with_requests, _superadmin

pytestmark = pytest.mark.django_db
LABEL = "hardware_requests.HardwareRequest"


def _find(space, term, *, exact):
    field = "requester_contact_email" if exact else "requester_name"
    return set(indexed_candidates(makerspace_id=space.pk, model_label=LABEL, field_name=field, term=term, exact=exact))


def test_a_space_without_its_own_key_keeps_the_deployment_key():
    with enabled_encryption():
        space, rows = _space_with_requests(1)
        assert write_key(space.pk) == (None, search_key())
        assert set(PiiBlindIndex.objects.filter(object_id=rows[0].pk).values_list("space_key_version", flat=True)) == {None}
        assert _find(space, rows[0].requester_contact_email, exact=True) == {rows[0].pk}


def test_keys_differ_per_space_and_per_version():
    with enabled_encryption():
        salt = b"\x01" * 32
        assert derive(1, 1, salt) != derive(2, 1, salt) != derive(1, 2, salt)


def test_rotation_reindexes_the_space_and_search_works_throughout():
    with enabled_encryption():
        space, rows = _space_with_requests(3)
        other, other_rows = _space_with_requests(1)
        job = start_search_key_rotation(_superadmin(), space)
        assert job.kind == "search_reindex" and job.to_version == 1
        assert [version for version, _ in search_keys(space.pk)] == [None, 1]  # building + the old key
        assert _find(space, rows[0].requester_contact_email, exact=True) == {rows[0].pk}
        assert _find(space, "Ada 1", exact=False) >= {rows[1].pk}
        _run_to_completion()
        job.refresh_from_db()
        assert job.status == "completed"
        key = MakerspaceSearchKey.objects.get(makerspace=space, version=1)
        assert key.status == "active"
        assert set(PiiBlindIndex.objects.filter(makerspace=space).values_list("space_key_version", flat=True)) == {1}
        assert _find(space, rows[2].requester_contact_email, exact=True) == {rows[2].pk}
        assert _find(space, "Ada 2", exact=False) >= {rows[2].pk}
        # The new hash is not the deployment-key hash: an archive holder with the global key alone
        # cannot test an address against this space's index.
        stored = PiiBlindIndex.objects.get(makerspace=space, object_id=rows[2].pk, field_name="requester_contact_email")
        global_hash = exact_hash(rows[2].requester_contact_email, generation=stored.search_generation.generation,
                                 makerspace_id=space.pk, model_label=LABEL, field_name="requester_contact_email")
        assert bytes(stored.exact_hash) != global_hash
        # Other spaces are untouched.
        assert set(PiiBlindIndex.objects.filter(makerspace=other).values_list("space_key_version", flat=True)) == {None}
        assert _find(other, other_rows[0].requester_contact_email, exact=True) == {other_rows[0].pk}
        assert AuditLog.objects.filter(makerspace=space, action="encryption.search_reindexed").exists()


def test_a_second_rotation_retires_the_first_key():
    with enabled_encryption():
        space, rows = _space_with_requests(1)
        start_search_key_rotation(_superadmin(), space)
        _run_to_completion()
        start_search_key_rotation(_superadmin(), space)
        _run_to_completion()
        statuses = dict(MakerspaceSearchKey.objects.filter(makerspace=space).values_list("version", "status"))
        assert statuses == {1: "retired", 2: "active"}
        assert _find(space, rows[0].requester_contact_email, exact=True) == {rows[0].pk}


def test_search_key_rotation_needs_encryption_on():
    space, _rows = _space_with_requests(1)
    with pytest.raises(ValidationError):
        start_search_key_rotation(_superadmin(), space)
