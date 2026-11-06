"""Document delivery audit exposes references, never capability or PDF content."""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P


ENTRIES = (
    P("notification.media_grant_issued", gettext_lazy("Document delivery grant issued"), ("delivery_id", "document_id", "certificate_id")),
    P("notification.media_grant_consumed", gettext_lazy("Document delivery grant consumed"), ("delivery_id", "document_id", "certificate_id")),
    P("notification.media_grant_cleaned", gettext_lazy("Document delivery grant cleaned up"), ("grant_id",)),
)
