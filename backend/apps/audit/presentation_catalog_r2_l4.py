"""Presentation entries for release-2 lane L4 (membership lifecycle) audit actions."""

from .presentation_catalog_types import P

ENTRIES = (
    P("makerspace.financial_year_updated", "Financial year start month changed", ("from_month", "to_month")),
)
