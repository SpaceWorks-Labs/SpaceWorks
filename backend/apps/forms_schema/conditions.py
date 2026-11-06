"""Bounded declarative conditions over earlier, visible answers only."""
from django.utils.translation import gettext
import math
from django.core.exceptions import ValidationError

OPERATORS = frozenset({"eq", "ne", "in", "contains", "is_set"})


def validate_condition(node, earlier, *, depth=1, budget=None):
    budget = [0] if budget is None else budget
    if not isinstance(node, dict) or depth > 3:
        raise ValidationError(gettext("Conditions allow at most three levels."), code="invalid_condition")
    if set(node) in ({"all"}, {"any"}):
        key = next(iter(node))
        children = node[key]
        if not isinstance(children, list) or not 1 <= len(children) <= 20:
            raise ValidationError(gettext("Use 1–20 condition clauses."), code="invalid_condition")
        return {key: [validate_condition(child, earlier, depth=depth + 1, budget=budget)
                      for child in children]}
    if set(node) not in ({"field_id", "op"}, {"field_id", "op", "value"}):
        raise ValidationError(gettext("Unknown condition keys."), code="invalid_condition")
    budget[0] += 1
    if budget[0] > 20:
        raise ValidationError(gettext("Use at most 20 condition clauses."), code="invalid_condition")
    field_id, op = node["field_id"], node["op"]
    if not isinstance(field_id, str) or field_id not in earlier:
        raise ValidationError(gettext("Conditions must reference an earlier question."), code="invalid_condition")
    if earlier[field_id]["type"] in {"age_at_event", "date_of_birth"}:
        raise ValidationError(gettext("Age and birth dates cannot control eligibility."), code="age_gating_forbidden")
    if not isinstance(op, str) or op not in OPERATORS:
        raise ValidationError(gettext("Unsupported comparison."), code="invalid_condition")
    value = node.get("value")
    if op == "is_set":
        if "value" in node and type(value) is not bool:
            raise ValidationError(gettext("is_set takes a boolean."), code="invalid_condition")
    elif "value" not in node:
        raise ValidationError(gettext("Comparison value is required."), code="invalid_condition")
    elif op == "in":
        if not isinstance(value, list) or not 1 <= len(value) <= 50:
            raise ValidationError(gettext("in takes 1–50 values."), code="invalid_condition")
        if any(type(item) not in (str, int, float, bool) for item in value):
            raise ValidationError(gettext("Use primitive comparison values."), code="invalid_condition")
    elif type(value) not in (str, int, float, bool):
        raise ValidationError(gettext("Use a primitive comparison value."), code="invalid_condition")
    if ((isinstance(value, str) and len(value) > 5000)
            or (isinstance(value, list) and any(isinstance(item, str) and len(item) > 5000 for item in value))):
        raise ValidationError(gettext("Condition value is too long."), code="invalid_condition")
    _validate_operand(earlier[field_id], op, value)
    return dict(node)


def _validate_operand(question, op, value):
    if op == "is_set":
        return
    kind = question["type"]
    values = value if op == "in" else [value]
    options = {option["id"] for option in question.get("options", [])}
    for operand in values:
        valid = False
        if kind == "number" and op != "contains":
            try:
                valid = type(operand) in (int, float) and math.isfinite(operand)
            except OverflowError:
                valid = False
        elif kind == "yes_no" and op != "contains":
            valid = type(operand) is bool
        elif kind in {"single_choice", "multi_choice"}:
            valid = isinstance(operand, str) and operand in options and (
                kind == "single_choice" and op != "contains" or kind == "multi_choice" and op == "contains")
        elif kind in {"short_text", "long_text", "email", "phone", "url", "date"}:
            valid = isinstance(operand, str)
        if not valid:
            raise ValidationError(gettext("Comparison value must match its earlier question type."), code="invalid_condition")


def _comparison(value):
    if isinstance(value, dict) and "option_id" in value:
        return value["option_id"]
    if isinstance(value, dict) and "option_ids" in value:
        return value["option_ids"]
    return value


def _equal(left, right):
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    return left == right


def visible(condition, answers):
    if condition is None:
        return True
    if "all" in condition:
        return all(visible(child, answers) for child in condition["all"])
    if "any" in condition:
        return any(visible(child, answers) for child in condition["any"])
    key, op = condition["field_id"], condition["op"]
    present = key in answers
    if op == "is_set":
        return present == condition.get("value", True)
    if not present:
        return False
    answer, expected = _comparison(answers[key]), condition["value"]
    if op == "eq":
        return _equal(answer, expected)
    if op == "ne":
        return not _equal(answer, expected)
    if op == "in":
        return any(_equal(answer, item) for item in expected)
    if isinstance(answer, str):
        return isinstance(expected, str) and expected in answer
    return isinstance(answer, list) and any(_equal(expected, item) for item in answer)
