"""Executable G1 boundary fixtures; stdlib checks run without a database.

Run directly for model-free checks. The project pytest harness additionally runs
the real F baseline/add-on validator tests once F's owned files are integrated.
These fixtures describe future commands; they do not claim those workflows exist.
"""
import ast
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import importlib.util
import inspect
import json
from pathlib import Path
import re
import sys
import unittest
from uuid import UUID

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))
from apps.events.contracts.form_operations import child_form_operation_id
from apps.events.contracts.subjects import AnswerSubject, StageResponseSubject, SubjectKind
from apps.payments.currencies import normalize_supported_currency, supported_minor_unit_exponent

# profile_fields is model-free; package __init__ imports DRF. Load the real file
# directly so the stdlib contract run does not counterfeit a Django dependency.
_spec = importlib.util.spec_from_file_location("g1_profile_fields", BACKEND / "apps/forms_schema/profile_fields.py")
_profile = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _profile
_spec.loader.exec_module(_profile)
PROFILE_FIELDS = _profile.PROFILE_FIELDS

FIXTURE = Path(__file__).with_name("contracts") / "reimbursement_addon.json"
C = json.loads(FIXTURE.read_text(encoding="utf8"))


def validate_fixture(schema, value, root=None):
    """Validate the small closed JSON-schema subset used by these frozen fixtures."""
    root = schema if root is None else root
    if "$ref" in schema:
        target = root
        for key in schema["$ref"].removeprefix("#/").split("/"):
            target = target[key]
        return validate_fixture(target, value, root)
    if "const" in schema and (value != schema["const"] or type(value) is not type(schema["const"])):
        raise ValueError("const")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("enum")
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    actual = {dict: "object", list: "array", int: "integer", str: "string", bool: "boolean", type(None): "null"}.get(type(value))
    if types and actual not in types:
        raise ValueError("type")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if set(schema.get("required", [])) - value.keys():
            raise ValueError("required")
        if schema.get("additionalProperties") is False and value.keys() - properties.keys():
            raise ValueError("unknown")
        for key, item in value.items():
            if key in properties:
                validate_fixture(properties[key], item, root)
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError("minItems")
        for item in value:
            validate_fixture(schema.get("items", {}), item, root)
    elif type(value) is int and value < schema.get("minimum", value):
        raise ValueError("minimum")
    if isinstance(value, str) and "pattern" in schema and not re.fullmatch(schema["pattern"], value):
        raise ValueError("pattern")


class ReimbursementContractFixtures(unittest.TestCase):
    def test_existing_question_map_and_save_versions_use_real_standard_keys(self):
        form = C["form_envelope"]["base_input"]
        self.assertIsInstance(form["answers"], dict)
        self.assertEqual(set(form), set(C["form_envelope"]["member_keys"]))
        for form in [form, *C["submission"]["ordinary"]["payload"]["stage_forms"]]:
            self.assertTrue(set(form["save_choices"]) <= PROFILE_FIELDS.keys())
            for key, selected in form["save_choices"].items():
                if selected:
                    self.assertIn(key, form["saved_detail_versions"])
        for q in C["form_envelope"]["base_schema"]["questions"]:
            self.assertIn(q["profile_field_key"], PROFILE_FIELDS)
            self.assertIn(q["type"], PROFILE_FIELDS[q["profile_field_key"]].question_types)

    def test_child_vectors_are_stable_under_order_revision_and_answer_changes(self):
        inline = C["inline_forms"]
        seen = set()
        for slot, item in reversed(list(inline["operations"].items())):
            actual = child_form_operation_id(UUID(inline["outer_operation_id"]), event_id=41, owner_id=73, slot=slot)
            self.assertEqual(str(actual), item["operation_id"])
            seen.add(actual)
        self.assertEqual(len(seen), 3)
        self.assertNotIn(UUID(inline["outer_operation_id"]), seen)
        for slot in inline["invalid_slots"]:
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                child_form_operation_id(UUID(inline["outer_operation_id"]), event_id=41, owner_id=73, slot=slot)
        for bad in (True, 0, -1, "41"):
            with self.assertRaises(ValueError):
                child_form_operation_id(UUID(inline["outer_operation_id"]), event_id=bad, owner_id=73, slot="base")

    def test_stage_subject_is_separate_from_closed_age_enum_and_validates_binding(self):
        self.assertNotIn("stage_response", [kind.value for kind in SubjectKind])
        self.assertIsInstance(StageResponseSubject(**C["stages"]["subject"]), StageResponseSubject)
        virtual = {**C["stages"]["virtual_subject"]}
        virtual["creation_operation_id"] = UUID(virtual["creation_operation_id"])
        self.assertEqual(StageResponseSubject(**virtual).kind, "stage_response")
        for changes in ({"subject_id": None}, {"subject_id": True}, {"owner_member_id": 0},
                        {"kind": "payee"}, {"creation_operation_id": UUID(int=1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                StageResponseSubject(**{**C["stages"]["subject"], **changes})
        with self.assertRaises(ValueError):
            AnswerSubject(event_id=41, owner_member_id=73, kind="stage_response", subject_id=111)

    def test_statuses_binding_and_whole_command_rollback(self):
        inline = C["inline_forms"]
        for row in inline["statuses"]:
            self.assertEqual(row["operation_id"], inline["operations"][row["slot"]]["operation_id"])
            self.assertIn(row["operation_id"], row["status_url"])
        self.assertIsNone(inline["no_save"]["intent_id"])
        self.assertIsNone(inline["no_save"]["status_url"])
        self.assertFalse(inline["binding"]["http_proof"])
        self.assertEqual(inline["equal_save"]["second_status"], "unchanged")
        self.assertEqual(inline["conflict"]["expected"], "saved_detail_form_conflict")
        self.assertEqual(inline["rollback"]["existing_draft"], "unchanged")
        self.assertIn("request", inline["rollback"]["absent_after"])
        self.assertIn("outer receipt insert", inline["rollback"]["inject"])

    def test_both_complete_submissions_carry_base_two_stages_and_same_fixed_request(self):
        submit = C["submission"]
        for kind in ("ordinary", "application"):
            wrapper = submit[kind]
            body = wrapper["payload"]
            self.assertEqual(body["operation_id"], wrapper["idempotency_key"])
            self.assertEqual(body["expected_version"], 0)
            self.assertEqual([s["stage_form_id"] for s in body["stage_forms"]], [11, 12])
            self.assertTrue(all(s["save_choices"] for s in body["stage_forms"]))
            request = body["reimbursement_request"]
            self.assertIs(request["submit"], True)
            self.assertEqual(request["form"]["revision"], request["programme_version"])
            self.assertEqual(request["form"]["form_id"], f"reimbursement-request-{request['programme_id']}")
            self.assertEqual(sum(e["amount_minor"] for e in request["estimates"]), submit["mapping"]["estimated_total_minor"])
            for e in request["estimates"]:
                self.assertEqual(submit["mapped_form"]["answers"]["estimate_" + e["category"]],
                                 {"amount_minor": e["amount_minor"], "currency": e["currency"]})
        self.assertEqual(submit["ordinary"]["payload"]["reimbursement_request"], submit["application"]["payload"]["reimbursement_request"])
        self.assertEqual(submit["response_reference"]["reimbursement_request"], submit["request_reference"])
        self.assertEqual(submit["errors"]["same_key_altered_request"][0], 409)
        self.assertEqual(submit["errors"]["draft_or_answer_edit_or_consent_repair"], [400, "reimbursement_submit_only"])

    def test_stage_age_files_and_missing_coverage_cannot_be_bypassed_by_reconciliation(self):
        stages = C["stages"]
        self.assertEqual(stages["derivations"], {})
        self.assertEqual(stages["refusal"], {"code": "stage_age_question_unsupported", "status": 400})
        self.assertEqual(stages["file_context"]["purpose"], "stage_form_file")
        self.assertEqual(set(stages["forbidden_types"]), {"date_of_birth", "age_at_event"})
        for case in stages["missing_coverage"]:
            self.assertFalse(case["assignment_ids"])
            self.assertTrue(case["published_applicable_stage_ids"])
            self.assertEqual((case["status"], case["code"], case["side_effects"]), (409, "stage_incomplete", []))
        self.assertFalse(stages["offline"]["attendance_written"])
        for action in ("cancel", "reassign"):
            self.assertIs(stages[action]["body"]["confirmed"], True)
            self.assertIn("expected_response_version", stages[action]["body"])
        self.assertTrue(stages["cancel"]["exempts_guard"])
        self.assertIn("replacement_form_revision_id", stages["reassign"]["body"])

    def test_stage_details_freeze_callable_revision_specific_disclosure(self):
        detail = C["stages"]["detail"]
        self.assertNotEqual(detail["current_submitted_revision"], detail["selected_revision"])
        self.assertEqual(detail["organizer"]["authority"], ["manage_registrations", "VIEW_AUDIT"])
        self.assertEqual(detail["finance"]["authority"], ["VIEW_FINANCE"])
        self.assertEqual(detail["finance"]["projection"], "sensitive only")
        by_name = {r["name"]: r for r in C["routes"]}
        for purpose in ("organizer", "finance"):
            row = detail[purpose]
            self.assertEqual(by_name[row["route"]]["methods"], ["GET", "HEAD"])
            self.assertEqual(by_name[row["route"]]["serializer"], row["serializer"])

    def test_currency_cases_use_shared_normalizer_and_real_exponent_wrapper(self):
        for case in C["currencies"]["valid"]:
            self.assertEqual(normalize_supported_currency(case["input"]), case["normalized"])
            self.assertEqual(supported_minor_unit_exponent(case["input"]), case["exponent"])
        for value in C["currencies"]["invalid"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                supported_minor_unit_exponent(value)
        for row in C["currencies"]["rounding"]:
            value = Decimal(row["original_minor"]) / 10 ** row["original_exponent"]
            converted = value * Decimal(row["fx_rate"]) * 10 ** row["target_exponent"]
            self.assertEqual(int(converted.quantize(Decimal("1"), rounding=ROUND_HALF_UP)), row["converted_minor"])

    def test_initialization_has_one_fund_entry_and_patch_is_never_upsert(self):
        setup = C["initialization"]
        self.assertEqual(setup["first"]["fund_entries"], setup["same_policy"]["fund_entries"])
        self.assertEqual(setup["first"]["status"], 201)
        self.assertEqual(setup["same_policy"]["status"], 200)
        self.assertEqual(setup["concurrent_different_policy"], 409)
        self.assertFalse(setup["payload"]["initial_settings"]["enabled"])
        self.assertIn("never upsert", setup["PATCH_missing"])

    def test_closed_core_evidence_schemas_and_preserved_cancellation_digest(self):
        evidence = C["core_evidence"]
        for name in ("decision_summary", "cancellation_revision", "attachment_closure"):
            validate_fixture(C["schemas"][name], evidence[name])
            mutated = {**evidence[name], "bank_account": "forbidden"}
            with self.assertRaises(ValueError):
                validate_fixture(C["schemas"][name], mutated)
        for value in evidence["coordination"]:
            validate_fixture(C["schemas"]["coordination"], value)
            self.assertEqual(value["expected_pool_version"] is None, value["domain_coordination_state"] == "detached")
        encoded = json.dumps(evidence["cancellation_command"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.assertEqual(sha256(encoded.encode()).hexdigest(), evidence["cancellation_revision"]["command_digest"])
        summary = evidence["decision_summary"]
        self.assertEqual(sum(line["approved_minor"] for line in summary["lines"]), summary["totals"]["approved_minor"])
        self.assertLessEqual(summary["totals"]["approved_minor"], summary["award"]["cap_minor"])
        self.assertEqual(summary["lines"][0]["rounding"], "HALF_UP")
        self.assertIn("no domain lookup", evidence["detached_cancel"])

    def test_method_inventory_keeps_finance_live_session_only_and_no_owner_receipt_download(self):
        names, pairs = set(), set()
        for route in C["routes"]:
            self.assertNotIn(route["name"], names)
            names.add(route["name"])
            for method in route["methods"]:
                pair = (route["path"], method)
                self.assertNotIn(pair, pairs)
                pairs.add(pair)
            self.assertTrue(route["live_host"])
            if "/event-payouts" in route["path"]:
                self.assertTrue(route["session_only"])
                self.assertIsNone(route["module"])
        for name in ("finance-event-payout-record", "finance-event-payout-amend"):
            route = next(r for r in C["routes"] if r["name"] == name)
            self.assertEqual(route["authority"], "VIEW_FINANCE AND RECORD_REIMBURSEMENT_PAYOUT")
            self.assertTrue(route["recent_reauth"])
        self.assertNotIn("member-event-receipt-file-download", names)
        self.assertIn("finance-event-payout-cancel", names)

    def test_mandatory_fields_lock_order_purge_and_removed_exports(self):
        crypto = C["mandatory_encryption"]
        self.assertEqual(crypto["fields"]["payments.EventPayeeRevision"], ["details"])
        self.assertEqual(C["lock_order"][:4], ["source lock-only boundary", "global PII shared fence", "tenant fences sorted", "account fences sorted"])
        self.assertLess(C["lock_order"].index("budget pools sorted"), C["lock_order"].index("obligation"))
        self.assertEqual(set(C["purge_preflight"]["keys"]), {"events", "event_reimbursements"})
        self.assertFalse(C["retained_contracts"]["account_zip_addition"])
        self.assertFalse(C["retained_contracts"]["automatic_transfers"])


@unittest.skipUnless(importlib.util.find_spec("django"), "Django unavailable; run in isolated backend harness")
class RealFormsCompatibility(unittest.TestCase):
    def test_existing_v1_and_question_map_v2_still_execute(self):
        from apps.forms_schema.submission import validate_submission
        legacy = C["legacy"]
        result = validate_submission(schema=legacy["V1_SCHEMA"], payload={"answers": legacy["V1_INPUT"]})
        self.assertIsNotNone(result.snapshot)
        result = validate_submission(schema=C["form_envelope"]["base_schema"], payload=C["form_envelope"]["base_input"])
        self.assertEqual(result.profile_values["name"], "A Maker")

    def test_f_addon_money_file_itinerary_and_stage_age_execute(self):
        from apps.forms_schema.schema_v2 import validate_schema
        from apps.forms_schema.submission import validate_submission
        if "context" not in inspect.signature(validate_submission).parameters:
            self.skipTest("F-owned add-on implementation not integrated at G1; run on F/integrated tree")
        legacy = C["legacy"]
        result = validate_submission(schema=legacy["CLAIM_SCHEMA"], payload=legacy["CLAIM_INPUT"],
                                     context="claim", file_resolver=lambda **kw: True)
        self.assertEqual(result.snapshot["answers"][0]["value"]["currency"], "INR")
        validate_schema(legacy["STAGE_SCHEMA"], context="stage")
        for kind in C["stages"]["forbidden_types"]:
            schema = {"schema_version": 2, "form_id": "stage", "revision": 1, "questions": [
                {"id": "q", "type": kind, "label": "Question", "required": False}]}
            with self.subTest(kind=kind), self.assertRaises(Exception) as caught:
                validate_schema(schema, context="stage")
            self.assertEqual(caught.exception.code, "stage_age_question_unsupported")


if __name__ == "__main__":
    unittest.main()
