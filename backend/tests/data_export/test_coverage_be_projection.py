"""COVERAGE-BE: CSV projection helpers (archive.py) and the raw PII collector (pii_raw.py), branch by branch."""
import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.apps import apps

from apps.data_export import archive, pii_raw
from apps.data_export.errors import ExportIntegrityError
from apps.data_export.types import Redacted, Transformed
from apps.encryption import registry


# ------------------------------------------------------------------ csv_value
@pytest.mark.parametrize("value,expected", [
    (None, ""),
    ({"b": 1, "a": "é"}, '{"a":"é","b":1}'),
    ([1, "x"], '[1,"x"]'),
    ((1, 2), "[1,2]"),
    (datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc), "2026-01-02T03:04:05+00:00"),
    (date(2026, 1, 2), "2026-01-02"),
    (time(3, 4), "03:04:00"),
    (Decimal("1.250"), "1.250"),
    (True, "true"),
    (False, "false"),
    (7, "7"),
    ("text", "text"),
])
def test_csv_value_exact_rendering(value, expected):
    assert archive.csv_value(value) == expected


# ---------------------------------------------------- strip_sensitive_url_parts
@pytest.mark.parametrize("value,expected", [
    (None, None),
    ("", ""),
    ("https://user:pw@maps.example.com:8443/p/q?token=s#frag", "https://maps.example.com:8443/p/q"),
    ("https://maps.example.com/p?x=1", "https://maps.example.com/p"),
    ("not a url", ""),
    ("https:///nohost", ""),
])
def test_strip_sensitive_url_parts_drops_credentials_query_fragment(value, expected):
    assert archive.strip_sensitive_url_parts(value) == expected


# ------------------------------------------------------ redact_custom_answers
def test_redact_custom_answers_by_answer_type_without_mutating_input():
    source = {"answers": [
        {"type": "short_text", "value": "secret"},
        {"type": "paragraph", "value": "secret2"},
        {"type": "number", "value": 4},
        {"type": "yes_no", "value": True},
        {"type": "signature", "value": "sig"},
        "not-a-dict",
    ]}
    out = archive.redact_custom_answers(source)
    assert [a["value"] if isinstance(a, dict) else a for a in out["answers"]] == [
        "[REDACTED_FREE_TEXT]", "[REDACTED_FREE_TEXT]", 4, True, "[REDACTED_UNKNOWN_TYPE]", "not-a-dict"]
    assert source["answers"][0]["value"] == "secret"


@pytest.mark.parametrize("value,expected", [
    (None, None),
    ("raw string", {"custom_answers_redacted": True}),
    ({"answers": "nope"}, {"custom_answers_redacted": True}),
    ({}, {"custom_answers_redacted": True}),
])
def test_redact_custom_answers_malformed_shapes(value, expected):
    assert archive.redact_custom_answers(value) == expected


# ------------------------------------------------------------ transform_value
def _red(marker="pii"):
    return Redacted(marker)


def test_transform_value_redaction_markers_and_audit_meta():
    assert archive.transform_value("audit.AuditLog", "meta", _red(), {"k": "v"}) == {"meta_redacted": True}
    assert archive.transform_value("x.Y", "notes", _red("secret_text"), "hi") == "[SECRET_TEXT]"
    assert archive.transform_value("x.Y", "custom_answers", _red(), None) is None


def test_transform_value_application_answers_json_string_and_bad_json():
    good = json.dumps({"answers": [{"type": "short_text", "value": "v"}]})
    out = archive.transform_value("x.Y", "application_answers", _red(), good)
    assert out["answers"][0]["value"] == "[REDACTED_FREE_TEXT]"
    assert archive.transform_value("x.Y", "application_answers", _red(), "{broken") == {
        "custom_answers_redacted": True}


def test_transform_value_plain_disposition_passthrough_and_url_and_theme():
    assert archive.transform_value("x.Y", "name", object(), "keep") == "keep"
    transformed = Transformed("note")
    assert archive.transform_value("x.Y", "map_url", transformed, "https://u:p@h.example/p?q=1") == "https://h.example/p"
    assert archive.transform_value("x.Y", "link", transformed, "bad") == ""
    theme = {"mode": "dark", "primary_color": "#000", "secret": "x", "logo_url": "u"}
    assert archive.transform_value("makerspaces.Makerspace", "theme_config", transformed, theme) == {
        "mode": "dark", "primary_color": "#000", "logo_url": "u"}
    assert archive.transform_value("makerspaces.Makerspace", "theme_config", transformed, "str") == {}
    assert archive.transform_value("x.Y", "other", transformed, 5) == 5


def test_transform_value_external_reference_needs_writer(monkeypatch):
    monkeypatch.setattr(archive, "EXTERNAL_REFERENCES", {("x.Y", "ref"): object()})
    transformed = Transformed("note")
    with pytest.raises(ExportIntegrityError, match="requires the external-reference writer"):
        archive.transform_value("x.Y", "ref", transformed, "v")
    writer = SimpleNamespace(project=lambda row, source, value: f"proj:{source}:{value}")
    assert archive.transform_value("x.Y", "ref", transformed, "v", row=None, external_writer=writer) == "proj:ref:v"


# --------------------------------------------------------------- source_value
def test_source_value_follows_relations_and_returns_fk_attname_at_terminal():
    user_model = apps.get_model("accounts.User")
    owner = user_model(pk=11, username="owner")
    job = apps.get_model("data_export.DataExportJob")(requested_by=owner)
    assert archive.source_value(job, "requested_by") == 11  # terminal relation -> raw id, no fetch
    assert archive.source_value(job, "requested_by__username") == "owner"
    assert archive.source_value(job, "fidelity") == "REDACTED"
    job.download_issued_to = None
    assert archive.source_value(job, "download_issued_to__username") is None  # broken chain -> None


# ------------------------------------------------------------------- pii_raw
def _direct_field():
    return next(f for f in registry.ALL_FIELDS if f.makerspace_path == "makerspace_id")


def _row(makerspace_id=5, pk=9, raw="x"):
    field = _direct_field()
    model = apps.get_model(field.model_label)
    instance = model(pk=pk, makerspace_id=makerspace_id)
    instance.__dict__[model._meta.get_field(field.field_name).attname] = raw
    return field, instance


def test_mapped_field_names_and_select_related_paths_follow_registry():
    field = _direct_field()
    assert field.field_name in pii_raw.mapped_field_names(field.model_label)
    assert pii_raw.mapped_field_names("nope.Missing") == ()
    paths = {p for f in registry.ALL_FIELDS for p in pii_raw.select_related_paths(f.model_label)}
    assert all(isinstance(p, str) and "." not in p for p in paths)
    assert "makerspace_id" not in paths


def test_raw_value_refuses_a_deferred_mapped_field():
    field, row = _row()
    attname = row._meta.get_field(field.field_name).attname
    del row.__dict__[attname]
    with pytest.raises(ExportIntegrityError, match="has deferred mapped field"):
        pii_raw.raw_value(row, field.field_name)


def test_aad_inputs_refuse_unmapped_field_and_deferred_pk_and_return_bindings():
    field, row = _row(makerspace_id=5, pk=9)
    assert pii_raw.aad_inputs(row, field.field_name) == {
        "makerspace_id": 5, "table": row._meta.db_table, "pk": 9, "field": field.field_name}
    with pytest.raises(ExportIntegrityError, match="is not a mapped PII field"):
        pii_raw.aad_inputs(row, "id")
    del row.__dict__[row._meta.pk.attname]
    with pytest.raises(ExportIntegrityError, match="deferred source primary key"):
        pii_raw.aad_inputs(row, field.field_name)


def test_collector_register_model_ignores_unmapped_models_and_registers_mapped():
    collector = pii_raw.PiiAadCollector(5)
    collector.register_model("nope.Missing")
    assert collector._models == {}
    field = _direct_field()
    collector.register_model(field.model_label)
    entry = collector._models[field.model_label]
    assert field.field_name in entry["fields"] and entry["rows"] == {}


def test_collector_refuses_foreign_tenant_plain_text_and_malformed_envelopes():
    field, foreign = _row(makerspace_id=6, pk=1, raw="")
    collector = pii_raw.PiiAadCollector(5)
    with pytest.raises(ExportIntegrityError, match="belongs to makerspace 6, not 5"):
        collector.project(foreign, field.field_name)
    _f, plain = _row(makerspace_id=5, pk=2, raw="plaintext@example.test")
    with pytest.raises(ExportIntegrityError, match="is not an encrypted PII envelope"):
        collector.project(plain, field.field_name)
    from apps.encryption.crypto import _PREFIX
    _f, bad = _row(makerspace_id=5, pk=3, raw=_PREFIX + "!!!not-valid")
    with pytest.raises(ExportIntegrityError, match="has a malformed PII envelope"):
        collector.project(bad, field.field_name)
    _f, empty = _row(makerspace_id=5, pk=4, raw="")
    assert collector.project(empty, field.field_name) == ""
    assert collector._models[field.model_label]["rows"] == {"4": 5}


def test_collector_write_emits_sorted_aad_inputs(tmp_path):
    field, row = _row(makerspace_id=5, pk=4, raw="")
    collector = pii_raw.PiiAadCollector(5)
    collector.project(row, field.field_name)
    collector.write(tmp_path)
    payload = json.loads((tmp_path / "pii" / "aad_inputs.json").read_text(encoding="utf-8"))
    assert payload["models"][0]["label"] == field.model_label
    assert payload["models"][0]["rows"] == {"4": 5}
