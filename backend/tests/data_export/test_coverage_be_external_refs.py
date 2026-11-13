"""COVERAGE-BE: refusal and record-shape branches of the portable external-reference writer.

Rows are light stand-ins exposing only `_meta.label`, `pk` and attributes: these branches are about the
writer's own validation, and the full-row flows are proved in test_portable_external_refs.py.
"""
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from apps.data_export import external_refs
from apps.data_export.errors import ExportIntegrityError
from apps.data_export.external_refs import ExternalReferenceWriter

pytestmark = pytest.mark.django_db

OWN = 5


def row(label, pk=1, **attrs):
    meta = SimpleNamespace(label=label, get_field=lambda name: SimpleNamespace(attname=f"{name}_id"))
    return SimpleNamespace(_meta=meta, pk=pk, **attrs)


def records(writer):
    writer.close()
    return [json.loads(line) for line in writer.path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def writer(tmp_path, monkeypatch):
    w = ExternalReferenceWriter(tmp_path, OWN)
    monkeypatch.setattr(w, "_validate_snapshot", lambda label, field, snap: None)
    yield w
    if not w._handle.closed:
        w.close()


def test_writer_refuses_when_tenant_migration_is_tombstoned(tmp_path, monkeypatch):
    monkeypatch.setattr(external_refs, "runtime_active", lambda key: False)
    with pytest.raises(ExportIntegrityError, match="requires the tenant_migration module"):
        ExternalReferenceWriter(tmp_path, OWN)


def test_project_refuses_unknown_edge(writer):
    with pytest.raises(ExportIntegrityError, match="Unknown external reference edge"):
        writer.project(row("x.Unknown"), "makerspace", 7)


def test_project_passes_empty_values_through_and_refuses_a_dangling_reference(writer):
    label, field = ("events.EventCollaborator", "makerspace")
    assert writer.project(row(label), field, None) is None
    assert writer.project(row(label), field, "") == ""
    with pytest.raises(ExportIntegrityError, match=r"has makerspace=7 but no such row"):
        writer.project(row(label, makerspace=None), field, 7)


def test_project_keeps_local_reference_and_writes_foreign_one_with_event_anchor(writer):
    label, field = ("events.EventCollaborator", "makerspace")
    local = row(label, pk=3, makerspace=SimpleNamespace(pk=OWN, name="own", slug="own"),
                event_id=40, event=SimpleNamespace(_meta=SimpleNamespace(label="events.Event")))
    assert writer.project(local, field, OWN) == OWN
    foreign = row(label, pk=4, makerspace=SimpleNamespace(pk=99, name="Other", slug="other"),
                  event_id=41, event=SimpleNamespace(_meta=SimpleNamespace(label="events.Event")))
    assert writer.project(foreign, field, 99) is None
    assert records(writer) == [{
        "source_model_label": label, "source_object_id": "4", "field_name": "makerspace",
        "target_model_label": "events.Event", "target_object_id": "41",
        "snapshot": {"name": "Other", "slug": "other"}}]


def test_project_series_collaborator_anchors_on_the_series(writer):
    label = "events.EventSeriesCollaborator"
    foreign = row(label, pk=6, makerspace=SimpleNamespace(pk=77, name="N", slug="n"), series_id=12,
                  series=SimpleNamespace(_meta=SimpleNamespace(label="events.EventSeries")))
    assert writer.project(foreign, "makerspace", 77) is None
    (record,) = records(writer)
    assert (record["target_model_label"], record["target_object_id"]) == ("events.EventSeries", "12")


def test_project_rejects_a_snapshot_the_schema_refuses(tmp_path):
    w = ExternalReferenceWriter(tmp_path, OWN)

    def refuse(label, field, snap):
        raise ValueError("bad shape")
    w._validate_snapshot = refuse
    foreign = row("events.EventCollaborator", pk=8, makerspace=SimpleNamespace(pk=1, name="n", slug="s"),
                  event_id=1, event=SimpleNamespace(_meta=SimpleNamespace(label="events.Event")))
    with pytest.raises(ExportIntegrityError, match="row 8 has an invalid makerspace snapshot"):
        w.project(foreign, "makerspace", 1)
    w.close()


def test_write_record_anchor_forms_and_validation_failure(writer):
    r = row("events.EventCollaborator", pk=9)
    writer._write_record(r, "makerspace", {"k": 1}, anchor=None)
    writer._write_record(r, "makerspace", {"k": 2}, anchor=SimpleNamespace(
        _meta=SimpleNamespace(label="events.Event"), pk=50))
    first, second = records(writer)
    assert (first["target_model_label"], first["target_object_id"]) == ("events.EventCollaborator", "9")
    assert (second["target_model_label"], second["target_object_id"]) == ("events.Event", "50")

    def refuse(label, field, snap):
        raise ValueError("no")
    writer._validate_snapshot = refuse
    with pytest.raises(ExportIntegrityError, match="row 9 has an invalid makerspace snapshot"):
        writer._write_record(r, "makerspace", {}, anchor=None)


def test_withhold_identity_records_a_pii_free_edge(writer):
    r = row("events.EventRegistration", pk=11)
    r.member_id = 321
    writer.withhold_identity(r, "member")
    (record,) = records(writer)
    assert record == {
        "source_model_label": "events.EventRegistration", "source_object_id": "11", "field_name": "member",
        "target_model_label": "accounts.User", "target_object_id": "321",
        "snapshot": {"kind": "withheld_identity"}}


def test_snapshot_shapes_per_edge_kind():
    starts = datetime(2026, 5, 1, 9, tzinfo=timezone.utc)
    ends = datetime(2026, 5, 1, 11, tzinfo=timezone.utc)
    event = SimpleNamespace(title="Jam", starts_at=starts, ends_at=ends)
    assert external_refs._snapshot(("events.EventCollaborator", "event"), event) == {
        "title": "Jam", "starts_at": starts.isoformat(), "ends_at": ends.isoformat()}
    series = SimpleNamespace(title="Weekly")
    assert external_refs._snapshot(("events.EventSeriesCollaborator", "series"), series) == {"title": "Weekly"}
    container = SimpleNamespace(label="Shelf", makerspace=SimpleNamespace(name="M", slug="m"))
    assert external_refs._snapshot(("operations.StockTransfer", "source_container"), container) == {
        "label": "Shelf", "makerspace": {"name": "M", "slug": "m"}}
    plain = SimpleNamespace(name="M", slug="m")
    assert external_refs._snapshot(("events.EventCollaborator", "makerspace"), plain) == {"name": "M", "slug": "m"}


def test_owner_makerspace_id_uses_target_owner_for_container_event_series_else_own_pk():
    related = SimpleNamespace(pk=1, makerspace_id=2)
    for edge in (("operations.StockTransfer", "destination_container"), ("events.EventCollaborator", "event"),
                 ("events.EventSeriesCollaborator", "series")):
        assert external_refs._owner_makerspace_id(edge, related) == 2
    assert external_refs._owner_makerspace_id(("events.EventCollaborator", "makerspace"), related) == 1


def test_select_related_paths_cover_container_event_and_series_models():
    assert {"source_container", "source_container__makerspace"} <= external_refs.select_related_paths(
        "operations.StockTransfer")
    assert "event" in external_refs.select_related_paths("events.EventCollaborator")
    assert "series" in external_refs.select_related_paths("events.EventSeriesCollaborator")
    assert external_refs.select_related_paths("inventory.Category") == set()
