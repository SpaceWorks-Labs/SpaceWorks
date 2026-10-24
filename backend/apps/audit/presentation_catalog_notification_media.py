"""Document delivery audit exposes references, never capability or PDF content."""

from .presentation_catalog_types import P


ENTRIES = (
    P("notification.media_grant_issued", "Document delivery grant issued", ("delivery_id", "document_id", "certificate_id")),
    P("notification.media_grant_consumed", "Document delivery grant consumed", ("delivery_id", "document_id", "certificate_id")),
    P("notification.media_grant_cleaned", "Document delivery grant cleaned up", ("grant_id",)),
)
