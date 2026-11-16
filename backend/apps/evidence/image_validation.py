from io import BytesIO

from PIL import Image, UnidentifiedImageError


IMAGE_MIME_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def image_mime_from_bytes(data):
    try:
        image = Image.open(BytesIO(data))
        detected = IMAGE_MIME_BY_FORMAT.get(image.format)
        image.verify()
    except (OSError, UnidentifiedImageError):
        return None
    return detected


# Release 2 L5 (owner decision #155): a finance-ledger RECEIPT may also be a PDF. Only the
# `receipt` evidence type admits it; issue and return evidence stay images-only. The key
# carries the type (`evidence/<space>/<type>/<uuid>`, staging under `staging/`), so the
# storage validators decide from the object key alone.
PDF_MIME = "application/pdf"
RECEIPT_EXTRA_MIME = (PDF_MIME,)


def is_receipt_key(object_key):
    parts = str(object_key or "").removeprefix("staging/").split("/")
    return len(parts) >= 4 and parts[0] == "evidence" and parts[2] == "receipt"


def pdf_mime_from_bytes(data):
    """A structurally plausible PDF: the header first and an end-of-file marker at the end."""
    if data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]:
        return PDF_MIME
    return None


def allowed_mime_for_key(object_key, image_mime):
    """The MIME types an object at this key may hold (images, plus PDF for receipts)."""
    return (*image_mime, *RECEIPT_EXTRA_MIME) if is_receipt_key(object_key) else tuple(image_mime)


def detect_mime_for_key(object_key, data):
    detected = image_mime_from_bytes(data)
    if detected is None and is_receipt_key(object_key):
        detected = pdf_mime_from_bytes(data)
    return detected
