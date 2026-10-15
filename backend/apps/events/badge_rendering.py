"""Event field adapter over the always-present printable PDF engine."""

from apps.operations.printable_layout import page_layout
from apps.operations.printable_pdf import render_sheet


def render_badges_pdf(template, snapshots, *, title):
    # Only authorized field values cross this seam; no bearer credential enters it.
    rows = [dict(zip(template["fields"], (value for _label, value in snapshot.fields)))
            for snapshot in snapshots]
    return render_sheet(template, rows, title=title, layout=page_layout)
