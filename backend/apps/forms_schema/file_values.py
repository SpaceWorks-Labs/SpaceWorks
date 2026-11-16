"""Closed file references. Domain adapters own authorization and attachment."""
import re
from .profile_fields import ProfileValueError

PURPOSES = {"stage": "stage_form_file", "claim": "reimbursement_receipt",
            "payee": "reimbursement_payee_document"}
FINANCE_PURPOSES = frozenset(PURPOSES.values()) - {"stage_form_file"}


def file_schema(raw):
    if (not isinstance(raw, dict) or set(raw) != {"purpose", "max_files", "max_bytes_each"}
            or not isinstance(raw["purpose"], str) or raw["purpose"] not in PURPOSES.values()
            or type(raw["max_files"]) is not int or not 1 <= raw["max_files"] <= 5
            or type(raw["max_bytes_each"]) is not int or not 1 <= raw["max_bytes_each"] <= 10_485_760):
        raise ProfileValueError("Configure a supported file purpose, 1–5 files and at most 10 MiB each.")
    return dict(raw)


def normalize_files(question, value):
    if not isinstance(value, list) or len(value) > question["file"]["max_files"]:
        raise ProfileValueError("Use a bounded array of ready file references.")
    result, seen = [], set()
    for ref in value:
        if (not isinstance(ref, dict) or set(ref) != {"asset_id", "generation", "sha256"}
                or any(type(ref[key]) is not int or not 1 <= ref[key] <= 9_007_199_254_740_991
                       for key in ("asset_id", "generation"))
                or not isinstance(ref["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", ref["sha256"])
                or ref["asset_id"] in seen):
            raise ProfileValueError("Use unique ready file references with generation and SHA-256.")
        seen.add(ref["asset_id"])
        result.append(dict(ref))
    return result


def resolve_files(question, value, resolver):
    """Resolver must recheck owner/event/question/purpose/readiness/hash/size/MIME.

    It raises ProfileValueError on refusal. This pure preparation step never
    attaches bytes; the domain rechecks and attaches once inside its transaction.
    """
    if resolver is None:
        raise ProfileValueError("This form has no authorized file provider.")
    for reference in value:
        if resolver(question=question, reference=dict(reference)) is not True:
            raise ProfileValueError("This file is unavailable in the current form context.")
