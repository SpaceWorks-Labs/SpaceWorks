"""Booking semantics over the shared paginated report renderer."""

from .report_pdf import render_pdf as render_report_pdf


def render_pdf(rows, *, provenance, title):
    return render_report_pdf(
        rows, provenance=provenance,
        title=f"{title} - calendar reservation occupancy (not measured physical use)",
    )
