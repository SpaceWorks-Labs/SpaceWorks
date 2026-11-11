"""Literal registry handoff cannot silently omit a field, User edge or G1 model."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).parents[4] / "apps" / "events"


def test_manifest_enumerates_every_concrete_field_and_user_edge():
    manifest = json.loads((ROOT / "judging/model_manifest.json").read_text(encoding="utf8"))
    rows = {row["model"].split(".")[-1]: row for row in manifest["models"]}
    inherited = {"EventOwned": {"event", "version"}, "PrivateRecord": {"makerspace"}}
    found = set()
    files = [p for p in (ROOT / "judging").glob("models_*.py") if p.name != "models_base.py"]
    files.append(ROOT / "submissions/gallery_models.py")
    for path in files:
        for node in ast.parse(path.read_text(encoding="utf8")).body:
            if not isinstance(node, ast.ClassDef):
                continue
            found.add(node.name)
            fields = {"id"}
            for base in node.bases:
                fields |= inherited.get(ast.unparse(base), set())
            user_edges = set()
            for item in node.body:
                if (isinstance(item, ast.Assign) and isinstance(item.value, ast.Call)
                        and ast.unparse(item.value.func).startswith(("models.", "MoneyDecimalField"))):
                    name = item.targets[0].id
                    fields.add(name)
                    if "settings.AUTH_USER_MODEL" in ast.unparse(item.value):
                        user_edges.add(name)
            assert set(rows[node.name]["fields"]) == fields, node.name
            assert set(rows[node.name]["user_edges"]) == user_edges, node.name
            assert rows[node.name]["owned_object_fields"] == []
    assert found == set(rows)


def test_all_frozen_g1_d_model_identities_are_present_and_consent_has_one_owner():
    manifest = json.loads((ROOT / "judging/model_manifest.json").read_text(encoding="utf8"))
    checkpoint = Path(__file__).parents[1] / "contracts/fixtures/model-provider-manifest-v3.json"
    frozen = json.loads(checkpoint.read_text(encoding="utf8"))
    actual = {row["model"].split(".")[-1] for row in manifest["models"]}
    expected = {row["name"] for row in frozen["models"] if row["lane"] == "D"}
    assert expected <= actual
    assert "ParticipantSponsorResumeConsent" in actual and "ParticipantSponsorConsent" not in actual
    assert manifest["migration_owner"] == "G"
