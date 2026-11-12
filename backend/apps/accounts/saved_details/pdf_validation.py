"""Bounded structural PDF checks; résumé originals never execute server content."""
from django.utils.translation import gettext
import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

from .errors import SavedDetailsError

_ACTIVE = {"/JS", "/JavaScript", "/OpenAction", "/AA", "/EmbeddedFiles", "/EmbeddedFile", "/Launch", "/RichMedia", "/XFA", "/GoToR"}


def validate_pdf(data):
    def invalid():
        return SavedDetailsError("invalid_pdf", gettext("Use an unencrypted PDF of at most 100 pages without active content."))
    if not data.startswith(b"%PDF-"):
        raise invalid()
    try:
        document = PdfReader(io.BytesIO(data), strict=True)
        if document.is_encrypted or not 1 <= len(document.pages) <= 100:
            raise invalid()
        stack, seen, count = [(document.trailer, 0)], set(), 0
        while stack:
            node, depth = stack.pop()
            count += 1
            if count > 50_000 or depth > 50:
                raise invalid()
            if isinstance(node, IndirectObject):
                identity = (node.idnum, node.generation)
                if identity in seen:
                    continue
                seen.add(identity)
                stack.append((node.get_object(), depth + 1))
            elif isinstance(node, DictionaryObject):
                if _ACTIVE.intersection(node) or str(node.get("/S", "")) in _ACTIVE:
                    raise invalid()
                stack.extend((value, depth + 1) for value in node.values())
            elif isinstance(node, ArrayObject):
                stack.extend((value, depth + 1) for value in node)
    except (PdfReadError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise invalid() from exc
