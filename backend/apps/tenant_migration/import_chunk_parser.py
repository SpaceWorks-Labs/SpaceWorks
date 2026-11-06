"""Bound chunk memory even when a permission inspects request.data early."""

from django.utils.translation import gettext
import re

from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser

CHUNK_MAX_BYTES = 8 * 1024 * 1024


class OffsetChunkParser(BaseParser):
    media_type = "application/offset+octet-stream"

    def parse(self, stream, media_type=None, parser_context=None):
        request = parser_context["request"]
        raw_length = request.META.get("CONTENT_LENGTH", "")
        if not re.fullmatch(r"[0-9]{1,20}", str(raw_length)):
            raise ParseError(gettext("Content-Length must specify the chunk size."))
        length = int(raw_length)
        if not 1 <= length <= CHUNK_MAX_BYTES:
            raise ParseError(gettext('Content-Length must be between 1 and {CHUNK_MAX_BYTES}.').format(CHUNK_MAX_BYTES=CHUNK_MAX_BYTES))
        remaining, parts = length, []
        while remaining:
            part = stream.read(remaining)
            if not part:
                raise ParseError(gettext("The chunk body is shorter than Content-Length."))
            parts.append(part)
            remaining -= len(part)
        return b"".join(parts)
