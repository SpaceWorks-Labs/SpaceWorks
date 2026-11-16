"""Static items of a form-v2 schema: section headings (parity O-B2).

A heading carries no answer, so it is NOT a question: it lives in an optional top-level `sections` list and is
anchored to the question it appears above. Every consumer that walks `questions` (answer validation, conditions,
snapshots, exports, the Events forms) therefore keeps working unchanged and never sees a heading; only a renderer
that wants headings asks for `schema_items`. A schema without `sections` is exactly what it was before.

    "sections": [{"id": "about", "before": "<question id>", "heading": "About you", "help": "optional text"}]

A heading is shown when at least one question below it (up to the next heading) is visible; that rule lives in
the renderer because visibility needs the live answers.
"""
import re

MAX_SECTIONS = 20
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_KEYS = {"id", "before", "heading", "help"}


def _fail(message):
    from .schema_v2 import fail
    fail(message)


def validate_sections(raw, question_ids):
    """Normalised copy of `raw`; every heading must sit above a real question and ids must be unique."""
    if not isinstance(raw, list) or len(raw) > MAX_SECTIONS:
        _fail(f"Use at most {MAX_SECTIONS} section headings.")
    seen, result = set(), []
    for item in raw:
        if not isinstance(item, dict) or set(item) - _KEYS or not {"id", "before", "heading"} <= set(item):
            _fail("A section needs an id, a heading and the question it sits above.")
        sid = item["id"]
        if not isinstance(sid, str) or not _ID.fullmatch(sid) or sid in seen or sid in question_ids:
            _fail("Use unique stable section IDs.")
        if item["before"] not in question_ids:
            _fail("A section must sit above an existing question.")
        seen.add(sid)
        entry = {"id": sid, "before": item["before"], "heading": _text(item["heading"], 120, blank=False)}
        if "help" in item:
            entry["help"] = _text(item["help"], 1000, blank=True)
        result.append(entry)
    return result


def _text(value, maximum, *, blank):
    if not isinstance(value, str) or len(value.strip()) > maximum or (not blank and not value.strip()):
        _fail(f"Use {'0' if blank else '1'}-{maximum} characters.")
    return value.strip()


def schema_items(schema):
    """Questions and headings in render order: [{"kind": "section"|"question", ...}]."""
    if not isinstance(schema, dict):
        return []
    sections = {}
    for section in schema.get("sections") or []:
        sections.setdefault(section["before"], []).append(section)
    items = []
    for question in schema.get("questions", []):
        items.extend({"kind": "section", **section} for section in sections.get(question["id"], []))
        items.append({"kind": "question", **question})
    return items


def reanchor_sections(schema, kept_questions):
    """Headings for a filtered question list: one above a removed question moves to the next kept one.

    A heading with no kept question below it is dropped (nothing to introduce).
    """
    kept = {question["id"] for question in kept_questions}
    order = [question["id"] for question in schema.get("questions", [])]
    result = []
    for section in schema.get("sections") or []:
        start = order.index(section["before"]) if section["before"] in order else len(order)
        target = next((qid for qid in order[start:] if qid in kept), None)
        if target is not None:
            result.append({**section, "before": target})
    return result
