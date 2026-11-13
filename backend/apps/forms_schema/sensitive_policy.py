"""Context policy and authorized projections, without account or model access."""
from django.utils.translation import gettext
from copy import deepcopy
from django.core.exceptions import ValidationError
from .file_values import PURPOSES, FINANCE_PURPOSES

def validate_context(schema, *, context=None, derivations=None):
    """Context is supplied by the installed domain provider, never a descriptor."""
    if context is not None and context not in PURPOSES:
        raise ValidationError(gettext("Unknown server form context."), code="invalid_form_context")
    questions = schema.get("questions", [])
    if context == "stage":
        ids = [q.get("id") for q in questions if isinstance(q, dict) and (
            q.get("type") in ("date_of_birth", "age_at_event") or q.get("profile_field_key") in ("date_of_birth", "age_at_event")
            or "derivation" in q or "derivation_binding" in q)]
        if ids or derivations or schema.get("derivations"):
            safe_ids = [qid for qid in ids if isinstance(qid, str) and len(qid) <= 64
                        and qid.isascii() and all(c.isalnum() or c in "_-" for c in qid)]
            raise ValidationError(gettext("Stage forms do not support DOB or age: ") + ", ".join(safe_ids),
                                  code="stage_age_question_unsupported")
    for question in questions:
        if not isinstance(question, dict) or question.get("type") != "file":
            continue
        config = question.get("file")
        purpose = config.get("purpose") if isinstance(config, dict) else None
        if context is None or purpose != PURPOSES[context]:
            raise ValidationError(gettext("File purpose is unavailable in this form context."), code="file_purpose_not_allowed")
        if purpose in FINANCE_PURPOSES and not question.get("sensitive"):
            raise ValidationError(gettext("Finance files must be sensitive."), code="sensitive_disclosure_required")


def validate_sensitive(questions):
    earlier = {}
    def check(node):
        if "field_id" in node:
            source = earlier[node["field_id"]]
            if source.get("sensitive"):
                raise ValidationError(gettext("Sensitive answers cannot control other questions."), code="sensitive_condition_forbidden")
        else:
            for child in node.get("all", node.get("any", [])):
                check(child)
    for question in questions:
        if question.get("sensitive") and any(question["disclosure"].values()):
            raise ValidationError(gettext("Sensitive answers are visible only to the owner and finance."),
                                  code="sensitive_disclosure_required")
        if question.get("show_if"):
            check(question["show_if"])
        earlier[question["id"]] = question


def permitted_questions(schema, *, viewer, current_schema=None):
    """The caller authorizes the viewer. Finance alone sees sensitive answers only.

    Intersect historical and live disclosure so withdrawing permission takes
    effect immediately, without rewriting immutable response revisions.
    """
    if viewer not in {"owner", "finance", "organizer", "reviewer", "judge"}:
        return []
    current = {q["id"]: q for q in (current_schema or schema)["questions"]}
    result = []
    for question in schema["questions"]:
        live = current.get(question["id"])
        if live is None:
            continue
        sensitive = question.get("sensitive", False) or live.get("sensitive", False)
        if (viewer == "owner" or viewer == "finance" and sensitive or not sensitive
                and viewer in {"organizer", "reviewer", "judge"}
                and question.get("disclosure", {}).get(viewer, viewer == "organizer")
                and live.get("disclosure", {}).get(viewer, viewer == "organizer")):
            result.append(question)
    return result


def project_schema(schema, *, viewer, current_schema=None):
    result = deepcopy(schema)
    current = {q["id"]: q for q in (current_schema or schema)["questions"]}
    result["questions"] = deepcopy(permitted_questions(schema, viewer=viewer, current_schema=current_schema))
    for question in result["questions"]:
        question["sensitive"] = question.get("sensitive", False) or current[question["id"]].get("sensitive", False)
        if viewer != "owner":
            question.pop("show_if", None)
            question.pop("profile_field_key", None)
    return result


def project_answers(schema, snapshot, *, viewer, current_schema=None, file_projector=None):
    """Never pass raw file IDs or derivation sources to staff; adapters supply links."""
    permitted = {q["id"]: q for q in permitted_questions(schema, viewer=viewer, current_schema=current_schema)}
    rows = []
    for row in snapshot.get("answers", []):
        question = permitted.get(row.get("id"))
        if question is None or "derivation_id" in row:
            continue
        result = {"id": question["id"], "label": question["label"], "type": question["type"]}
        if question["type"] == "file":
            if file_projector is None:
                continue
            result["value"] = file_projector(question=question, references=deepcopy(row.get("value", [])))
        else:
            result["value"] = deepcopy(row.get("value"))
        rows.append(result)
    return {"version": 2, "form_id": schema["form_id"], "form_revision": schema["revision"], "answers": rows}
