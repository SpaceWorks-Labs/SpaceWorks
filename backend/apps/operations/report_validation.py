"""Fail closed on report privacy declarations and the catalog chart contract."""

from string import Formatter

from django.core import checks


def validate_report_definition(definition):
    from .org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS

    for flag in ("platform_only", "identity_bearing"):
        if not isinstance(getattr(definition, flag), bool):
            raise ValueError(f"{flag} must be boolean.")
    if definition.identity_bearing:
        if definition.deployment_aggregate or definition.schedulable:
            raise ValueError("Identity-bearing reports must be tenant-only and unschedulable.")
        if definition.key not in EXCLUDED_ORGANIZATION_REPORT_KEYS:
            raise ValueError("Identity-bearing reports require an organization exclusion.")
    if definition.platform_only and (not definition.deployment_aggregate or definition.schedulable):
        raise ValueError("Platform-only reports must be deployment aggregates and unschedulable.")
    validate_chart_spec(definition.chart_spec, definition.fields)


def validate_chart_spec(spec, fields):
    """All keys are required; nullable currency/partition/truncation are explicit.

    series is a list of dimension field names; values is a nonempty list of
    {field, unit}. Units are display labels, not conversions. Alt placeholders
    reference declared fields (plus count); attribute/index traversal is forbidden.
    """
    if spec is None:
        return
    keys = {"series", "x", "values", "currency_field", "partition", "negatives", "truncation", "alt_template"}
    if not isinstance(spec, dict) or set(spec) != keys:
        raise ValueError("chart_spec must declare exactly the F1 keys.")

    def field(value):
        if not isinstance(value, str) or value not in fields:
            raise ValueError("Chart field must be a declared report field.")

    def text(value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Chart labels must be nonempty strings.")

    series = spec["series"]
    if not isinstance(series, list) or any(not isinstance(v, str) for v in series) or len(set(series)) != len(series):
        raise ValueError("series must be a list of distinct fields.")
    for value in series:
        field(value)
    x = spec["x"]
    if not isinstance(x, dict) or set(x) != {"field", "kind"} or x["kind"] not in ("time", "category"):
        raise ValueError("x requires field and kind (time or category).")
    field(x["field"])
    if not isinstance(spec["values"], list) or not spec["values"]:
        raise ValueError("values must be a nonempty list.")
    value_fields = []
    for value in spec["values"]:
        if not isinstance(value, dict) or set(value) != {"field", "unit"}:
            raise ValueError("Each value requires field and unit.")
        field(value["field"])
        text(value["unit"])
        value_fields.append(value["field"])
    if len(set(value_fields)) != len(value_fields):
        raise ValueError("Value fields must be distinct.")
    if spec["currency_field"] is not None:
        field(spec["currency_field"])
    if spec["partition"] not in (None, "tenant", "currency", "unit"):
        raise ValueError("Unknown chart partition.")
    if spec["partition"] == "currency" and spec["currency_field"] is None:
        raise ValueError("Currency partition requires currency_field.")
    if spec["partition"] == "tenant" and "makerspace_id" not in fields:
        raise ValueError("Tenant partition requires makerspace_id.")
    if spec["negatives"] not in ("allow", "clip"):
        raise ValueError("negatives must be allow or clip.")
    truncation = spec["truncation"]
    if truncation is not None:
        if not isinstance(truncation, dict) or set(truncation) != {"top_n", "other_label"}:
            raise ValueError("truncation requires top_n and other_label.")
        if type(truncation["top_n"]) is not int or truncation["top_n"] < 1:
            raise ValueError("top_n must be a positive integer.")
        text(truncation["other_label"])
    text(spec["alt_template"])
    for _, name, format_spec, conversion in Formatter().parse(spec["alt_template"]):
        if name is not None and (name not in (*fields, "count") or format_spec or conversion):
            raise ValueError("Alt placeholders must be plain declared fields or count.")


@checks.register(checks.Tags.models)
def check_report_definitions(app_configs=None, **kwargs):
    from .report_registry import REPORT_REGISTRY
    errors = []
    for definition in REPORT_REGISTRY.values():
        try:
            validate_report_definition(definition)
        except ValueError as exc:
            errors.append(checks.Error(f"Report {definition.key!r}: {exc}", id="operations.E005"))
    return errors
