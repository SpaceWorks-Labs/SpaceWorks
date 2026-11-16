"""Shared matching for conditional target row policies."""

from collections.abc import Mapping


def condition_matches(condition, row):
    if condition is None:
        return True
    field_name, expected = condition
    if field_name == "_staff_account" and not isinstance(row, Mapping):
        from .portable_staff import is_staff_row
        actual = is_staff_row(row._meta.label, row)
    else:
        actual = row.get(field_name, False if field_name == "_staff_account" else "") if isinstance(row, Mapping) else getattr(
            row, field_name, ""
        )
    actual = str(actual).lower()
    if isinstance(expected, (tuple, list, set, frozenset)):
        return actual in {str(value).lower() for value in expected}
    return actual == str(expected).lower()
