"""Disposition names and the fragment composer for ``accounts.merge_registry``.

A fragment is a tuple of ``(disposition, model_label, field_names, reason)`` rows;
``field_names`` is space-separated so one model's fields share a line. A row whose
model label starts with ``#`` lists integer user-id columns (no foreign key) instead of
relations. Duplicates are refused at import so two fragments can never disagree.
"""

REPOINT = "repoint"
KEEP_ON_SHELL = "keep_on_shell"
UNIQUE_RESOLVE = "unique_resolve"
DISPOSITIONS = frozenset({REPOINT, KEEP_ON_SHELL, UNIQUE_RESOLVE})
COLUMN_PREFIX = "#"


def compose(*fragments):
    relations, columns = {}, {}
    for fragment in fragments:
        for disposition, label, names, reason in fragment:
            if disposition not in DISPOSITIONS or not reason.strip():
                raise ValueError(f"Merge registry row for {label} needs a disposition and a reason.")
            target = columns if label.startswith(COLUMN_PREFIX) else relations
            label = label.removeprefix(COLUMN_PREFIX)
            for name in names.split():
                if (label, name) in relations or (label, name) in columns:
                    raise ValueError(f"Duplicate merge registry row: {label}.{name}")
                target[(label, name)] = disposition
    return relations, columns
