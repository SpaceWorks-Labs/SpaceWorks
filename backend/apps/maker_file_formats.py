"""Compatibility imports. Strict event validation is deliberately opt-in."""
from apps.maker_formats.legacy import (
    ALLOWED_EXTENSIONS_BY_MIME, SIGNATURE_SNIFF_BYTES, STRICT_MIME_BY_EXTENSION,
    ZIP_LOCAL_FILE_MAGIC, allowed_pair, extension_from_name, has_required_signature,
    sniff_pdf_or_image,
)

__all__ = [
    "ALLOWED_EXTENSIONS_BY_MIME", "SIGNATURE_SNIFF_BYTES", "STRICT_MIME_BY_EXTENSION",
    "ZIP_LOCAL_FILE_MAGIC", "allowed_pair", "extension_from_name",
    "has_required_signature", "sniff_pdf_or_image",
]
