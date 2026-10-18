"""Bounded structural PDF parse; no rendering, JavaScript or attachment execution."""
from tempfile import SpooledTemporaryFile

from pypdf import PdfReader
from .errors import FormatError


def check_pdf(reader):
    try:
        with SpooledTemporaryFile(max_size=8 * 1024 ** 2) as handle:
            for chunk in reader.chunks():
                handle.write(chunk)
            handle.seek(0)
            document = PdfReader(handle, strict=True)
            if document.is_encrypted or not 1 <= len(document.pages) <= 3000:
                raise FormatError("invalid_pdf")
            # Interactive actions and embedded files are never required for a
            # submission PDF. Refuse them rather than executing or sanitizing.
            root = document.trailer["/Root"]
            if any(key in root for key in ("/OpenAction", "/AA", "/AcroForm")):
                raise FormatError("unsafe_pdf")
            names = root.get("/Names")
            if names and any(key in names.get_object() for key in ("/JavaScript", "/EmbeddedFiles")):
                raise FormatError("unsafe_pdf")
    except FormatError:
        raise
    except Exception as exc:
        raise FormatError("invalid_pdf") from exc
