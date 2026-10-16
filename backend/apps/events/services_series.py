"""Stable explicit import surface for series templates and projection."""

from .services_series_templates import (
    TEMPLATE_FIELDS, RECURRENCE_FIELDS, SERIES_FIELDS, occurrence_inherited_value,
    _validate, _event_values, _project_authority, _materialize_locked, _apply_template,
    create_series, extend_series, timezone,
)
from .services_series_update import update_series


from apps.events.services_series_lifecycle import (  # noqa: E402
    cancel_series,
    complete_series,
    publish_series,
)
