import json
import secrets
from copy import deepcopy
from types import SimpleNamespace

import pytest

from apps.encryption.crypto import encrypt, decrypt, PiiAuthenticationFailed
from apps.events.answer_derivations.portability import remap_canonical_answers
from apps.tenant_migration.pii_events_programme import rebind_programme_document


def canonical():
    return {"version": 2, "form_id": "stable-form", "form_revision": 4, "answers": [
        {"id": "age", "label": "Age", "type": "age_at_event", "derivation_id": 19},
        {"id": "resume", "type": "asset_reference", "value": {"asset_id": 31, "sha256": "a" * 64}},
        {"id": "note", "type": "short_text", "value": {"derivation_id": 19, "asset_id": 31}},
    ]}


def test_canonical_descriptors_remap_without_rewriting_text_or_storing_age():
    source = canonical()
    result = remap_canonical_answers(source, lambda label, value: value + 100)
    assert result["answers"][0]["derivation_id"] == 119
    assert "value" not in result["answers"][0]
    assert result["answers"][1]["value"]["asset_id"] == 131
    assert result["answers"][2] == source["answers"][2]
    assert source == canonical()


@pytest.mark.parametrize("value", [True, "19", 0, -1])
def test_invalid_typed_ids_refuse(value):
    source = canonical()
    source["answers"][0]["derivation_id"] = value
    with pytest.raises(ValueError):
        remap_canonical_answers(source, lambda *args: 123)


@pytest.mark.parametrize("label,name", [
    ("events.HackathonApplication", "answers_snapshot"),
    ("events.HackathonApplicationAnswerRevision", "answers_snapshot"),
    ("events.EventRoleAssignment", "answers"),
    ("events.EventRoleAnswerRevision", "answers"),
    ("events.HackathonSubmission", "form_answers"),
])
def test_authenticated_canonical_document_is_remapped_then_bound_to_target_aad(label, name):
    key = secrets.token_bytes(32)
    model = SimpleNamespace(_meta=SimpleNamespace(label=label, db_table="events_private_fixture"))
    raw = encrypt(json.dumps(canonical()).encode(), key, key_version=2, makerspace_id=9,
                  table=model._meta.db_table, pk=12, field=name)
    rebound, plain = rebind_programme_document(model, name, raw, source={"id": 12}, row={"id": 112},
        source_id=9, target_id=29, deks={2: key}, map_id=lambda label, value: value + 100)
    assert json.loads(plain)["answers"][0]["derivation_id"] == 119
    assert decrypt(rebound, key, makerspace_id=29, table=model._meta.db_table, pk=112, field=name).decode() == plain
    with pytest.raises(PiiAuthenticationFailed):
        decrypt(rebound, key, makerspace_id=9, table=model._meta.db_table, pk=12, field=name)


def test_project_hash_recomputed_from_remapped_plaintext_and_original_hash_retained():
    key = secrets.token_bytes(32)
    model = SimpleNamespace(_meta=SimpleNamespace(label="events.SubmissionSnapshot", db_table="events_submissionsnapshot"))
    project = {"asset_ids": [1], "assets": [{"id": 1, "sha256": "a" * 64}], "links": [{"id": 3}],
               "form_answers": canonical(), "description": "19 is text"}
    source = {"id": 12, "sealed_member_ids": [9], "content_sha256": "b" * 64}
    raw = encrypt(json.dumps(project).encode(), key, key_version=1, makerspace_id=9,
                  table=model._meta.db_table, pk=12, field="project")
    row = {"id": 112}
    _, plain = rebind_programme_document(model, "project", raw, source=source, row=row,
        source_id=9, target_id=29, deks={1: key}, map_id=lambda label, value: value + 100)
    document = json.loads(plain)
    assert document["asset_ids"] == [101] and document["form_answers"]["answers"][0]["derivation_id"] == 119
    assert row["sealed_member_ids"] == [109] and row["source_content_sha256"] == "b" * 64
    assert row["content_sha256"] != source["content_sha256"]
    assert document["description"] == project["description"]
