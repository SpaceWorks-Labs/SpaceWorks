"""Event field adapter over the always-present printable PDF engine."""

from apps.operations.printable_layout import page_layout
from apps.operations.printable_pdf import render_sheet


def render_badges_pdf(template, snapshots, *, title):
    # Only authorized field values cross this seam; no bearer credential enters it.
    rows = [dict(zip(template["fields"], (value for _label, value in snapshot.fields)))
            for snapshot in snapshots]
    return render_sheet(template, rows, title=title, layout=page_layout)


def render_credential_badges_pdf(document, snapshots, *, resolver):
    """Only authorized event snapshots can reach typed QR/photo slots."""
    from io import BytesIO
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
    from .certificates.layer_rendering import draw_document
    from .certificates.print_snapshot import BadgeSnapshot
    output = BytesIO()
    canvas = Canvas(output, pagesize=(document["page_width_mm"]*mm, document["page_height_mm"]*mm), invariant=1)
    canvas.setTitle("Space Works event badges")
    for snapshot in snapshots:
        if not isinstance(snapshot, BadgeSnapshot):
            raise TypeError("Use an authorized event print snapshot.")
        def resource(layer):
            handle = (snapshot.credential_render_handle if layer["type"] == "event_credential_qr" else
                      snapshot.photo_render_handle if layer["type"] == "photo" else
                      int(snapshot.logo_artwork_revision) if layer["type"] == "logo" and snapshot.logo_artwork_revision else None)
            return resolver(handle) if handle is not None else None
        draw_document(canvas, document, dict(snapshot.authorized_fields), resource)
        canvas.showPage()
    canvas.save()
    return output.getvalue()
