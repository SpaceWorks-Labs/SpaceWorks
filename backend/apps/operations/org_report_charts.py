"""Project a report chart onto its strategy's combined output fields."""

from copy import deepcopy


def combined_chart_spec(definition, strategy):
    spec = deepcopy(definition.chart_spec)
    if spec is None:
        return None
    fields = set(strategy.total_fields)
    if spec["x"]["field"] not in fields or any(value["field"] not in fields for value in spec["values"]):
        return None
    spec["series"] = [field for field in spec["series"] if field in fields]
    if spec["partition"] == "tenant":
        spec["partition"] = None  # The breakdown still carries tenant provenance.
    spec["alt_template"] = "{count} combined observations"
    return spec
