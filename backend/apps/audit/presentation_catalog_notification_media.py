"""Document delivery audit exposes references, never capability or PDF content."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("notification.media_grant_issued", gettext_noop("Document delivery grant issued"), ("delivery_id", "document_id", "certificate_id")),
    P("notification.media_grant_consumed", gettext_noop("Document delivery grant consumed"), ("delivery_id", "document_id", "certificate_id")),
    P("notification.media_grant_cleaned", gettext_noop("Document delivery grant cleaned up"), ("grant_id",)),
)
