"""Shared provider/consumer invariants independent of lane domain implementation."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator
import pytest

from apps.events import urls_programme
from apps.events.contracts.providers import ReadPurpose
from apps.events.contracts.subjects import SubjectKind

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_shared_fixture_bytes_match_versioned_index():
    # v3 stays frozen; v4 pins only the files added after the v3 checkpoint.
    entries = [entry for name in ("fixture-index-v3.json", "fixture-index-v4.json") for entry in load(name)["files"]]
    assert sorted(entry["path"] for entry in entries) == sorted(
        path.name for path in FIXTURES.glob("*.json") if not path.name.startswith("fixture-index-")
    )
    for entry in entries:
        data = (FIXTURES / entry["path"]).read_bytes()
        assert len(data) == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]


def test_seed_documents_use_the_shared_layer_schema_and_exact_stock_inventory():
    schema = load("contract-schemas-v3.json")
    validator = Draft202012Validator({**schema, "$ref": "#/$defs/TemplateDocumentV2"})
    seeds = load("template-seed-v2.json")
    validator.validate(seeds["seed"]["document"])
    validator.validate(seeds["badge_seed"]["document"])
    assert set(seeds["stocks"]) == {"a6-portrait", "4x6", "3x4", "4x3", "cr80-portrait", "cr80-landscape"}
    assert seeds["counts"] == {"frontend_svg": 58, "packaged_svg": 12, "twin_pairs": 35,
                               "certificate_renders": 6, "badge_stock_renders": 36}


@pytest.mark.parametrize("name,definition,part", [
    ("form-v2.json", "FormV2", "schema"),
    ("form-v2.json", "MemberInput", "member_input"),
    ("application-admission-v3.json", "MemberInput", "request"),
    ("application-admission-v3.json", "AdmissionSelection", "request"),
    ("application-admission-v3.json", "CanonicalSnapshot", "canonical_snapshot"),
    ("selected-photo-v3.json", "PhotoSelection", "selection"),
    ("selected-photo-v3.json", "PhotoSelection", "no_photo"),
])
def test_frozen_examples_satisfy_structural_schemas(name, definition, part):
    schema = load("contract-schemas-v3.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator({**schema, "$ref": f"#/$defs/{definition}"})
    validator.validate(load(name)[part])


def test_age_snapshot_cannot_persist_numeric_value_and_emergency_is_a_compound():
    schema = load("contract-schemas-v3.json")
    validate = Draft202012Validator({**schema, "$ref": "#/$defs/CanonicalSnapshot"})
    snapshot = load("form-v2.json")["canonical_snapshot"]
    validate.validate(snapshot)
    snapshot["answers"][1]["value"] = 22
    assert list(validate.iter_errors(snapshot))
    compound = Draft202012Validator({**schema, "$ref": "#/$defs/EmergencyContact"})
    fixture = load("emergency-contact-v2.json")
    compound.validate(fixture["canonical"]["value"])
    assert list(compound.iter_errors("Fixture Contact"))
    assert list(compound.iter_errors({**fixture["canonical"]["value"], "email": "x@example.test"}))
    assert fixture["prefill_round_trip"]["save_defaults"]["emergency_contact"] is False


def test_route_names_paths_methods_and_openapi_are_one_contract():
    rows = load("routes-v3.json")["routes"]
    api = load("openapi-v3.json")
    assert all(count == 1 for count in Counter(row["name"] for row in rows).values())
    assert len(rows) == len(api["paths"])
    for row in rows:
        assert row["enabled"] is False
        assert set(api["paths"][row["path"]]) == {method.lower() for method in row["operations"]}
        for method, operation in row["operations"].items():
            contract = api["paths"][row["path"]][method.lower()]
            assert contract["x-django-name"] == row["name"]
            assert contract["x-authentication"] == operation["authentication"]
            assert str(operation["success"]) in contract["responses"]
            if method in ("GET", "HEAD"):
                assert operation["request_example"] is None
            if method == "HEAD":
                assert all("content" not in response for response in contract["responses"].values())
    context = next(row for row in rows if row["name"] == "events-programme-public-context")
    assert set(context["operations"]) == {"GET", "HEAD"}
    assert context["operations"]["GET"]["authentication"] == "active_member_account_no_membership_required"
    assert not any("member-shift-signup-approve" in row["name"] for row in rows)


def test_every_literal_frozen_route_name_is_published_without_replacing_existing_names():
    names = {row["name"] for row in load("routes-v3.json")["routes"]}
    source = load("contract-source-v3.json")["sections"]["http_and_services"]
    literal_names = set(re.findall(r"(?<![\w-])(events-programme-[a-z][a-z-]+|member-saved-[a-z-]+)", source))
    assert literal_names <= names
    assert {"member-event-ticket", "member-event-ticket-png", "member-event-checkin-qr",
            "member-event-certificate-download", "public-event-register",
            "admin-event-certificate-template", "admin-event-broadcast-cancel"} <= names
    assert "events-programme-admin-certificate-template" not in names


def test_consent_has_one_writer_and_profile_defaults_and_subjects_match():
    models = load("model-provider-manifest-v3.json")
    consent = models["consent"]
    assert consent["owner"] == "D"
    assert consent["workflow"] == "apps.events.judging.sponsor_consent_workflow"
    assert "ParticipantSponsorConsent" not in {model["name"] for model in models["models"]}
    canonical = [model for model in models["models"] if model["name"] == consent["model"]]
    assert len(canonical) == 1 and canonical[0]["lane"] == "D"
    profile = load("profile-role-age-v3.json")
    assert profile["subjects"] == [kind.value for kind in SubjectKind]
    assert profile["role_only_fixture"]["registration_id"] is None
    fields = load("profile-fields-v3.json")["descriptors"]
    assert {field["field_key"] for field in fields if field["persistable"]} == set(profile["saved_keys"])
    assert all(not field["default_save"] for field in fields if field["sensitive"])
    # The v3 file stays frozen; event reimbursements added the two finance read purposes after it.
    finance = {"finance_reimbursement_receipt", "finance_payee_document"}
    assert {purpose.value for purpose in ReadPurpose} == set(load("read-purpose-v3.json")["purposes"]) | finance


def test_integration_mounts_barrel_and_manifest_retains_historical_migration_baseline():
    assert urls_programme.urlpatterns
    leaves = load("migration-leaves-v3.json")
    assert leaves["leaves"]["events"] == ["0036_event_speakers"]
    assert leaves["head"] == "01ac3decc0d3f32817cbf8956bf8b26cc5d7e7e7"
    apps = Path(__file__).resolve().parents[4] / "apps"
    for app, migrations in leaves["leaves"].items():
        for migration in migrations:
            assert (apps / app / "migrations" / f"{migration}.py").exists()
