"""Closed G1 version-one decision evidence. Never accepts payee/form payloads."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re
from uuid import UUID

from apps.payments.currencies import normalize_supported_currency, supported_minor_unit_exponent
from .validation import closed, minor, reason_code, PayoutValidationError
from .wire import canonical, utc

CATEGORIES = frozenset(("rail", "air", "bus", "ground_transport", "lodging"))
LINE_KEYS = ("line_uuid", "category", "expense_date", "vendor", "description", "traveller",
    "original_amount_minor", "original_currency", "original_exponent", "fx_rate", "rate_date",
    "rate_source", "source_note", "currency", "target_exponent", "converted_minor", "approved_minor",
    "limits", "rounding", "reason_code", "reason", "receipt")
RECEIPT_KEYS = ("attachment_id", "generation", "sha256", "total_minor", "currency", "receipt_use_id",
    "receipt_use_version", "allocation_minor", "override_uuid", "override_allocation", "override_reason_code", "override_reason")
ELIGIBILITY_KEYS = ("registration_id", "attendance_revision", "checkin_event_id", "correction_watermark",
    "attestation_uuid", "project_snapshot_ref", "core_eligibility_revision")


def check(condition):
    if not condition:
        raise PayoutValidationError("invalid_decision_summary")


def identifier(value):
    check(isinstance(value, str))
    try:
        check(str(UUID(value)) == value)
    except (ValueError, AttributeError):
        raise PayoutValidationError("invalid_decision_summary") from None
    return value


def text(value, *, maximum=5000, nonempty=False):
    check(isinstance(value, str) and len(value) <= maximum and (not nonempty or bool(value.strip())))


def currency(value):
    try:
        check(normalize_supported_currency(value) == value)
    except ValueError:
        raise PayoutValidationError("invalid_decision_summary") from None
    return value


def iso_date(value):
    check(isinstance(value, str))
    try:
        check(date.fromisoformat(value).isoformat() == value)
    except ValueError:
        raise PayoutValidationError("invalid_decision_summary") from None


def eligibility(value):
    closed(value, ELIGIBILITY_KEYS)
    for key in ELIGIBILITY_KEYS[:4] + ("core_eligibility_revision",):
        if value[key] is not None:
            minor(value[key], zero=key in ("attendance_revision", "correction_watermark"))
    for key in ("attestation_uuid", "project_snapshot_ref"):
        if value[key] is not None:
            identifier(value[key])


def receipt(value, *, source_currency, original_minor):
    closed(value, RECEIPT_KEYS)
    for key in ("attachment_id", "generation", "total_minor", "receipt_use_id", "receipt_use_version", "allocation_minor"):
        minor(value[key])
    check(isinstance(value["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", value["sha256"]) is not None)
    check(value["currency"] == source_currency and value["allocation_minor"] == original_minor
          and value["allocation_minor"] <= value["total_minor"])
    text(value["override_reason"])
    check(isinstance(value["override_allocation"], list) and len(value["override_allocation"]) <= 500)
    if value["override_uuid"] is None:
        check(value["override_allocation"] == [] and value["override_reason_code"] == value["override_reason"] == "")
    else:
        identifier(value["override_uuid"])
        reason_code(value["override_reason_code"])
        check(value["override_allocation"] and value["override_reason"].strip())
        seen, total = set(), 0
        for item in value["override_allocation"]:
            closed(item, ("claim_uuid", "line_uuid", "original_amount_minor"))
            pair = (identifier(item["claim_uuid"]), identifier(item["line_uuid"]))
            check(pair not in seen)
            seen.add(pair)
            total += minor(item["original_amount_minor"])
        check(total <= value["total_minor"])


def line(value, *, target_currency):
    closed(value, LINE_KEYS)
    identifier(value["line_uuid"])
    check(isinstance(value["category"], str) and value["category"] in CATEGORIES)
    for key in ("expense_date", "rate_date"):
        iso_date(value[key])
    for key in ("vendor", "description", "traveller", "rate_source", "source_note", "reason"):
        text(value[key], nonempty=key in ("vendor", "description", "traveller", "rate_source"))
    check(value["rate_source"] in ("manual", "receipt"))
    reason_code(value["reason_code"])
    source = currency(value["original_currency"])
    check(currency(value["currency"]) == target_currency)
    for key in ("original_amount_minor", "converted_minor", "approved_minor", "original_exponent", "target_exponent"):
        minor(value[key], zero=True)
    check(value["original_exponent"] == supported_minor_unit_exponent(source))
    check(value["target_exponent"] == supported_minor_unit_exponent(target_currency))
    check(isinstance(value["fx_rate"], str) and re.fullmatch(r"[0-9]{1,16}(\.[0-9]{1,12})?", value["fx_rate"]) is not None)
    try:
        rate = Decimal(value["fx_rate"])
        check(rate.is_finite() and rate > 0 and (source != target_currency or rate == 1))
        with localcontext() as ctx:
            ctx.prec = 64
            converted = Decimal(value["original_amount_minor"]) * rate * Decimal(10) ** (
                value["target_exponent"] - value["original_exponent"])
            check(int(converted.quantize(Decimal(1), rounding=ROUND_HALF_UP)) == value["converted_minor"])
    except InvalidOperation:
        raise PayoutValidationError("invalid_decision_summary") from None
    closed(value["limits"], ("cap_minor",))
    minor(value["limits"]["cap_minor"], zero=True)
    check(value["approved_minor"] <= min(value["converted_minor"], value["limits"]["cap_minor"])
          and value["rounding"] == "HALF_UP")
    receipt(value["receipt"], source_currency=source, original_minor=value["original_amount_minor"])


def validate_summary(value):
    """Return an isolated validated snapshot; errors contain no rejected values."""
    closed(value, ("schema_version", "source", "decision", "award", "totals", "lines", "eligibility"))
    check(type(value["schema_version"]) is int and value["schema_version"] == 1)
    source, decision, award, totals = (value[k] for k in ("source", "decision", "award", "totals"))
    closed(source, ("claim_uuid", "claim_revision", "decision_uuid", "decision_sequence"))
    for key in ("claim_uuid", "decision_uuid"):
        identifier(source[key])
    for key in ("claim_revision", "decision_sequence"):
        minor(source[key])
    closed(decision, ("outcome", "decided_at", "actor_id", "reason_code", "reason"))
    check(decision["outcome"] in ("approved", "partially_approved", "rejected"))
    try:
        check(utc(datetime.fromisoformat(decision["decided_at"].replace("Z", "+00:00"))) == decision["decided_at"])
    except (ValueError, TypeError, AttributeError):
        raise PayoutValidationError("invalid_decision_summary") from None
    if decision["actor_id"] is not None:
        minor(decision["actor_id"])
    reason_code(decision["reason_code"])
    text(decision["reason"])
    closed(award, ("uuid", "cap_minor", "currency", "policy_revision", "rule_revision", "applied_rules"))
    identifier(award["uuid"])
    for key in ("cap_minor", "policy_revision", "rule_revision"):
        minor(award[key])
    target = currency(award["currency"])
    closed(award["applied_rules"], ("category_caps",))
    caps = closed(award["applied_rules"]["category_caps"], (), CATEGORIES)
    for cap in caps.values():
        minor(cap, zero=True)
    closed(totals, ("claimed_minor", "eligible_minor", "approved_minor"))
    for amount in totals.values():
        minor(amount, zero=True)
    check(totals["approved_minor"] <= totals["eligible_minor"] <= totals["claimed_minor"])
    check(totals["approved_minor"] <= award["cap_minor"])
    check(isinstance(value["lines"], list) and 1 <= len(value["lines"]) <= 100)
    seen, converted, approved, category_totals, allocations = set(), 0, 0, {}, {}
    for item in value["lines"]:
        line(item, target_currency=target)
        check(item["line_uuid"] not in seen)
        seen.add(item["line_uuid"])
        converted += item["converted_minor"]
        approved += item["approved_minor"]
        category = item["category"]
        category_totals[category] = category_totals.get(category, 0) + item["approved_minor"]
        r = item["receipt"]
        key = (r["receipt_use_id"], r["receipt_use_version"])
        old_total, allocated, metadata = allocations.get(key, (r["total_minor"], 0, (r["sha256"], r["currency"])))
        check((old_total, metadata) == (r["total_minor"], (r["sha256"], r["currency"])))
        allocations[key] = (old_total, allocated + r["allocation_minor"], metadata)
    check(converted == totals["claimed_minor"] and approved == totals["approved_minor"])
    check(all(amount <= caps.get(category, award["cap_minor"]) for category, amount in category_totals.items()))
    check(all(allocated <= total for total, allocated, _ in allocations.values()))
    check((approved == 0) == (decision["outcome"] == "rejected"))
    check(decision["outcome"] != "approved" or approved == totals["eligible_minor"] == totals["claimed_minor"])
    check(decision["outcome"] != "partially_approved" or 0 < approved < totals["claimed_minor"])
    eligibility(value["eligibility"])
    # Also rejects unserializable/cyclic input before any database write.
    check(len(canonical(value).encode("utf8")) <= 1_000_000)
    return deepcopy(value)
