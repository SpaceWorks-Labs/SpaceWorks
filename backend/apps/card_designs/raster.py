"""PNG = the PDF page rasterised by pdfium, so PNG and print can never disagree (Q6).

CR80 landscape at 300 dpi is 1011 x 638 px. The background is opaque.
"""
from io import BytesIO


def pdf_page_to_png(pdf_bytes, index=0, *, dpi=300):
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(pdf_bytes)
    try:
        page = document[index]
        try:
            width_pt, height_pt = page.get_size()
            bitmap = page.render(scale=dpi / 72, fill_color=(255, 255, 255, 255))
            image = bitmap.to_pil().convert("RGB")
            # PDFium rounds the bitmap up; trim to the exact pixel size of the stock at this dpi.
            exact = (round(width_pt * dpi / 72), round(height_pt * dpi / 72))
            if image.size != exact:
                image = image.crop((0, 0, min(exact[0], image.width), min(exact[1], image.height)))
        finally:
            page.close()
    finally:
        document.close()
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True, dpi=(dpi, dpi))
    return buffer.getvalue()


def png_size(png_bytes):
    from PIL import Image
    with Image.open(BytesIO(png_bytes)) as image:
        return image.size
