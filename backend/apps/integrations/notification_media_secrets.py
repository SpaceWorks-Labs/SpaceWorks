"""Query-free log redaction, including malformed or already-spent media bearers."""
import re

_MEDIA_PATH = re.compile(r"(/api/v1/integrations/notification-media/)[^/?\s]+(\.pdf)")


def redact_media_uri(value):
    return _MEDIA_PATH.sub(r"\1[redacted]\2", value or "")
