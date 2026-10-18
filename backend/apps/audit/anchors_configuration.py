"""Configured immutable audit anchor sink selection."""

from django.conf import settings

from .anchors_base import AnchorConfigurationError
from .anchors_http import HttpCollectorAnchorSink
from .anchors_object_storage import ObjectStorageAnchorSink


def configured_sink(read_budget=None):
    """The configured sink; ``read_budget`` (optional) caps its reads for one attempt."""
    from apps.backup.managed.audit_guard import guarded_anchor_sink
    backend = str(getattr(settings, "AUDIT_ATTESTATION_ANCHOR_BACKEND", "")).lower()
    try:
        if backend == "object_storage":
            return guarded_anchor_sink(ObjectStorageAnchorSink(read_budget=read_budget))
        if backend == "http":
            return guarded_anchor_sink(HttpCollectorAnchorSink(read_budget=read_budget))
    except (TypeError, ValueError) as exc:
        raise AnchorConfigurationError("The audit anchor settings are invalid.") from exc
    raise AnchorConfigurationError("AUDIT_ATTESTATION_ANCHOR_BACKEND is not configured.")
