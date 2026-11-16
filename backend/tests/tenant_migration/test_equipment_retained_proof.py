from types import SimpleNamespace

import pytest

from apps.tenant_migration import equipment_intent_preinsert as subject
from apps.tenant_migration.insertion_errors import PrimaryKeyMapUnavailable
from apps.tenant_migration.insertion_errors import ArchiveFormatError
from apps.tenant_migration.reference_state import EQUIPMENT_RETAINED_FIELD, ReferenceState


def test_reserved_mapping_and_coincident_tenant_row_without_insert_proof_is_unavailable(monkeypatch):
    monkeypatch.setattr(subject.apps, "get_model", lambda _label: object())
    monkeypatch.setattr(subject, "every_row", lambda _model: SimpleNamespace(filter=lambda **_kwargs: SimpleNamespace(exists=lambda: True)))
    pk_map = SimpleNamespace(lookup=lambda _model, _source: 42)
    refs = SimpleNamespace(equipment_materialized=lambda *_args: False)
    with pytest.raises(PrimaryKeyMapUnavailable):
        subject.retained_source("events.EventRegistration", 7, pk_map=pk_map, references=refs, target=SimpleNamespace(pk=2))


def test_actual_recorded_source_target_pair_is_still_tenant_checked(monkeypatch):
    monkeypatch.setattr(subject.apps, "get_model", lambda _label: object())
    monkeypatch.setattr(subject, "every_row", lambda _model: SimpleNamespace(filter=lambda **_kwargs: SimpleNamespace(exists=lambda: False)))
    refs = SimpleNamespace(equipment_materialized=lambda *_args: True)
    with pytest.raises(PrimaryKeyMapUnavailable):
        subject.retained_source("events.EventRegistration", 7, pk_map=SimpleNamespace(lookup=lambda *_args: 42), references=refs, target=SimpleNamespace(pk=2))


@pytest.mark.parametrize("path", ["migration/reference_provenance.jsonl", "migration/external_references.jsonl"])
def test_archive_cannot_forge_the_internal_materialized_marker(path):
    record = {"source_model_label": "events.EventRegistration", "source_object_id": "7", "field_name": EQUIPMENT_RETAINED_FIELD, "kind": "equipment_materialized", "detail": {"target_pk": "42"}}
    archive = SimpleNamespace(json_lines=lambda name: iter([record]) if name == path else iter([]))
    state = ReferenceState.__new__(ReferenceState)
    state._insert = lambda _batch: None
    with pytest.raises(ArchiveFormatError, match="reserved internal"):
        state._load(archive)


def test_missing_creator_mapping_is_cleared_before_generic_fk_remap(monkeypatch):
    monkeypatch.setattr(subject.apps, "get_model", lambda _label: object())
    def missing(*_args):
        raise PrimaryKeyMapUnavailable("missing identity")
    row = {"creator_id": 7, "imported_nonreplayable": False}
    assert subject.prepare_receipt_creator(row, SimpleNamespace(lookup=missing), SimpleNamespace(equipment_identity_resolved=lambda *_args: False))
    assert row["creator_id"] is None


def test_replayable_source_cannot_start_with_null_creator():
    with pytest.raises(ArchiveFormatError):
        subject.prepare_receipt_creator({"creator_id": None, "imported_nonreplayable": False}, object(), object())
