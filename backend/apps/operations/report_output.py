"""One disclosure projection for previews, downloads and scheduled artifacts."""

import logging
from datetime import date, datetime
from decimal import Decimal

from .report_types import ReportResult

logger = logging.getLogger(__name__)
# Provenance/measurement explanations are not row data. Keep their schema explicit
# so arbitrary builder metadata cannot become a second disclosure channel.
META_FIELDS = frozenset({
    "source", "grain", "rollup_through", "definition", "limitations", "history",
    "observed_at", "money_dates", "legacy_dates", "owed", "calendar", "tax",
    "basis", "row_cap", "arrival_counts_available",
    "context_dimensions_available",
})


def _warn(definition, unknown):
    if unknown:
        # Never log values: the dropped data may itself contain credentials/PII.
        logger.warning("report_output_fields_dropped", extra={
            "report_key": definition.key, "dropped_fields": sorted(map(str, unknown)),
        })


def project_report_output(definition, result):
    """Preserve builder column order, retaining only explicitly declared fields.

    Organization aggregation intentionally calls this AFTER combination: private
    denominator fields are calculation inputs, never public columns.
    """
    allowed = set(definition.fields)
    if isinstance(result, ReportResult):
        unknown = set(result.field_order) - allowed
        for record in result.records:
            unknown.update(set(record) - allowed)
        _warn(definition, unknown)
        fields = tuple(field for field in result.field_order if field in allowed)
        meta = {key: value for key, value in result.meta.items()
                if key in META_FIELDS and isinstance(value, (str, int, float, bool, date, datetime, Decimal, type(None)))
                and (key != "context_dimensions_available" or type(value) is bool)}
        _warn(definition, set(result.meta) - meta.keys())
        return ReportResult(fields, [{field: row.get(field) for field in fields} for row in result.records],
                            meta)
    if isinstance(result, dict):
        _warn(definition, set(result) - allowed)
        return {key: value for key, value in result.items() if key in allowed}
    if not result:
        return result
    header, *records = result
    _warn(definition, set(header) - allowed)
    indexes = [index for index, field in enumerate(header) if field in allowed]
    return [[header[index] for index in indexes], *[
        [row[index] for index in indexes] for row in records
    ]]
