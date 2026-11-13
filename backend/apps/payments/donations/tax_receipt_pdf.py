"""The tax receipt PDF (80G or any other scheme), built from the frozen receipt plus the gift's
encrypted fields.

Read at render time from the encrypted columns: the donor's name, address and PAN. The
PAN is printed in full only for the giver and for staff who may read the space's PII; a
superadmin without a PII window gets the masked form, like every other surface (#111 Q12).
"""

from decimal import Decimal
from functools import partial
from io import BytesIO

from .tax_receipts import mask_pan, payment_for


def returned_amount(donation):
    """Money actually returned on this gift (succeeded refunds, corrections counted once)."""
    from apps.payments.refund_policy import succeeded_total

    payment = payment_for(donation)
    return succeeded_total(payment) if payment is not None else Decimal("0")


def _issuer(space):
    from apps.payments.models import MakerspaceBillingSettings

    policy = MakerspaceBillingSettings.objects.filter(makerspace=space).first()
    return (getattr(policy, "legal_name", "") or space.name), getattr(policy, "address", "") or ""


def _exemption_lines(receipt):
    """One line per exemption the receipt cites; older 80G receipts carry only the flat keys."""
    rows = receipt.get("exemptions") or [{"label": f"Section {receipt.get('section', '80G')}",
                                          "number": receipt.get("registration_number", ""),
                                          "valid_from": receipt.get("valid_from", ""),
                                          "valid_until": receipt.get("valid_until", "")}]
    lines = []
    for row in rows:
        validity = " to ".join(part for part in (row.get("valid_from"), row.get("valid_until")) if part)
        lines.append(f"{row.get('label', '')}: {row.get('number', '')}" + (f" (valid {validity})" if validity else ""))
    return lines


def render_tax_receipt(donation, *, show_pan=True):
    from apps.operations.printable_text_fonts import FontScope

    with FontScope():
        return _render(donation, show_pan=show_pan)


def _render(donation, *, show_pan):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle

    from apps.operations.printable_pdf import document_paragraph

    receipt = donation.tax_receipt or {}
    style = ParagraphStyle("receipt", fontSize=9.5, leading=14, textColor=colors.HexColor("#142C2A"))
    heading = ParagraphStyle("heading", parent=style, fontSize=18, leading=24, spaceAfter=6)
    small = ParagraphStyle("small", parent=style, fontSize=8, leading=12, textColor=colors.HexColor("#5B6863"))

    def text(value, selected=style, bold=False):
        return document_paragraph(str(value), selected, bold=bold)

    name, address = _issuer(donation.makerspace)
    story = [text(receipt.get("legal_name") or name, heading, True), text(address, small)]
    if receipt.get("organization_registration_number"):
        story.append(text(f"Registration number: {receipt['organization_registration_number']}", small))
    if receipt.get("registrant_pan"):
        story.append(text(f"PAN of the institution: {receipt['registrant_pan']}", small))
    story.extend(text(line, small) for line in _exemption_lines(receipt))
    story.extend([Spacer(1, 6 * mm), text("Donation receipt", heading, True),
                  text(f"Receipt {receipt.get('number', '')}", bold=True),
                  text(f"Received on {receipt.get('received_on', '')}", small), Spacer(1, 5 * mm)])
    detail = donation.tax_detail
    pan = (detail.pan if show_pan else mask_pan(detail.pan)) if detail else ""
    rows = [("Received from", donation.donor_name), ("Address", detail.address if detail else "")]
    rows += [("PAN", pan)] if pan else []
    rows += [("Amount", f"{donation.currency.upper()} {receipt.get('amount', donation.amount)}")]
    returned = returned_amount(donation)
    if returned:
        # Audit 0.12.0 C-5: the frozen receipt keeps the gift as received, but money given back
        # is no gift; the PDF states it and the net, so a deduction is never claimed on it.
        net = max(Decimal(str(receipt.get("amount", donation.amount))) - returned, Decimal("0"))
        rows += [("Returned to donor", f"{donation.currency.upper()} {returned}"),
                 ("Net donation", f"{donation.currency.upper()} {net}")]
    rows += [("Towards", donation.campaign.name if donation.campaign_id else "General donation")]
    table = Table([[text(label, small, True), text(value or "-")] for label, value in rows],
                  colWidths=[38 * mm, 132 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#EFE6DB")),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.extend([table, Spacer(1, 6 * mm)])
    if receipt.get("note"):
        story.append(text(receipt["note"], small))
    story.append(text("This receipt is issued for a voluntary donation. No goods or services were provided "
                      "in return.", small))
    if receipt.get("signatory_name"):
        story.extend([Spacer(1, 10 * mm), text(receipt["signatory_name"], bold=True),
                      text(receipt.get("signatory_title", ""), small)])
    if receipt.get("footer"):
        story.extend([Spacer(1, 4 * mm), text(receipt["footer"], small)])
    output = BytesIO()
    SimpleDocTemplate(output, invariant=1, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm,
                      bottomMargin=20 * mm, title=receipt.get("number", "Donation receipt"), pageCompression=1).build(
        story, canvasmaker=partial(Canvas, invariant=1))
    return output.getvalue()


def pdf_response(donation, *, show_pan=True):
    from django.http import HttpResponse

    response = HttpResponse(render_tax_receipt(donation, show_pan=show_pan), content_type="application/pdf")
    number = (donation.tax_receipt or {}).get("number", f"donation-{donation.pk}").replace("/", "-")
    response["Content-Disposition"] = f'attachment; filename="{number}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response
