"""Typed, source-derived personal PDFs. Message JSON never selects an object.

Only provider callbacks import domain code. The ledger remains always available;
the optional certificate adapter is invoked only for a live Events source.
"""
from dataclasses import dataclass
from contextlib import ExitStack, contextmanager
from typing import Callable


class DocumentDeliveryError(ValueError):
    """Fixed diagnostic safe for the shared delivery attempt budget."""


@dataclass(frozen=True)
class AttachmentReference:
    source_kind: str
    document_id: int
    kind: str
    revision: str

    def __post_init__(self):
        if (self.source_kind not in {"payments.document", "events.certificate", "card_designs.card", "events.ticket"}
                or type(self.document_id) is not int or self.document_id < 1
                or not isinstance(self.kind, str) or not 1 <= len(self.kind) <= 32
                or not isinstance(self.revision, str) or not 1 <= len(self.revision) <= 64):
            raise DocumentDeliveryError("document_not_authorized")


@dataclass(frozen=True)
class AttachmentSource:
    references: Callable
    authorize: Callable
    render: Callable
    # Strict FK field on NotificationMediaGrant, never a content-type/object ID. None marks
    # an EMAIL-ONLY source (release 2 L3 card PDFs): it never mints a provider media grant.
    media_field: str | None
    tenant_ids: Callable | None = None


_SOURCES = {}


def register_source(kind, source):
    expected = {"payments.document": "document", "events.certificate": "certificate", "card_designs.card": None,
                "events.ticket": None}
    if not isinstance(source, AttachmentSource) or kind not in expected or expected[kind] != source.media_field:
        raise ValueError("Use a typed attachment media subject.")
    if kind in _SOURCES and _SOURCES[kind] != source:
        raise ValueError("Duplicate attachment source.")
    _SOURCES[kind] = source


def _payment_references(envelope):
    from apps.payments.document_delivery import attachment_references as references
    return tuple(AttachmentReference("payments.document", item["document_id"], item["kind"], str(envelope.revision))
                 for item in references(envelope))


def _payment_authorize(reference, **scope):
    from apps.payments.document_delivery import authorized_document
    from apps.payments.notifications_p2 import revision
    document = authorized_document({"document_id": reference.document_id, "kind": reference.kind}, **scope)
    if reference.revision != revision(document.pk, document.issued_at):
        raise DocumentDeliveryError("document_not_authorized")
    return document


def _payment_render(reference, **scope):
    from apps.payments.document_delivery import render_attachment as render
    return render({"document_id": reference.document_id, "kind": reference.kind}, **scope)


def _certificate_references(envelope):
    from .notification_certificate_media import references
    return references(envelope)


def _certificate_authorize(reference, **scope):
    from .notification_certificate_media import authorize
    return authorize(reference, **scope)


def _certificate_render(reference, **scope):
    from .notification_certificate_media import render
    return render(reference, **scope)


register_source("payments.document", AttachmentSource(
    _payment_references, _payment_authorize, _payment_render, "document", lambda doc: (doc.makerspace_id,)))
register_source("events.certificate", AttachmentSource(
    _certificate_references, _certificate_authorize, _certificate_render, "certificate",
    lambda doc: (doc.storage_makerspace_id,)))


def source_for(reference):
    if not isinstance(reference, AttachmentReference) or reference.source_kind not in _SOURCES:
        raise DocumentDeliveryError("document_not_authorized")
    return _SOURCES[reference.source_kind]


def media_source_for(reference):
    """Provider (chat) media retrieval: email-only sources are refused here."""
    source = source_for(reference)
    if source.media_field is None:
        raise DocumentDeliveryError("document_not_authorized")
    return source


def attachment_references(envelope):
    source = _SOURCES.get(envelope.source_kind)
    if source is None:
        return ()
    if not envelope.recipient_id or envelope.audience not in {"member", "requester"}:
        raise DocumentDeliveryError("document_not_authorized")
    references = source.references(envelope)
    if len(references) > 1 or any(item.source_kind != envelope.source_kind or
        str(item.document_id) != str(envelope.source_id) or item.revision != str(envelope.revision)
        for item in references):
        raise DocumentDeliveryError("document_not_authorized")
    return references


def authorized_attachment(reference, *, makerspace_id, recipient_id):
    if type(makerspace_id) is not int or makerspace_id < 1 or type(recipient_id) is not int or recipient_id < 1:
        raise DocumentDeliveryError("document_not_authorized")
    return source_for(reference).authorize(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)


def attachment_tenant_ids(reference, *, makerspace_id, recipient_id):
    """Discover all notification+storage source scopes before acquiring any lock."""
    source = source_for(reference)
    document = authorized_attachment(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    scopes = tuple(source.tenant_ids(document)) if source.tenant_ids else (makerspace_id,)
    if any(type(value) is not int or value < 1 for value in scopes):
        raise DocumentDeliveryError("document_not_authorized")
    return tuple(sorted({makerspace_id, *scopes}))


@contextmanager
def attachment_source_boundary(reference, *, makerspace_id, recipient_id):
    """Source locks use the lock-only connection; external I/O holds no row locks."""
    from apps.tenant_migration.gate_runtime import boundary_tenant_write
    scopes = attachment_tenant_ids(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    with ExitStack() as stack:
        for tenant_id in scopes:
            stack.enter_context(boundary_tenant_write(tenant_id))
        if attachment_tenant_ids(reference, makerspace_id=makerspace_id, recipient_id=recipient_id) != scopes:
            raise DocumentDeliveryError("document_not_authorized")
        yield


def _valid_png(filename, data):
    import re
    return (isinstance(filename, str) and filename.endswith(".png") and 1 <= len(filename) <= 255
            and not re.search(r'[\x00-\x1f\x7f"\\/]', filename) and isinstance(data, bytes)
            and data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) <= 5 * 1024 * 1024)


def render_attachment(reference, *, makerspace_id, recipient_id):
    from .notification_document_transport import validate_document
    from .notification_slack_http import ProviderFailure
    authorized_attachment(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    source = source_for(reference)
    result = source.render(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    if not isinstance(result, tuple) or len(result) != 3 or result[2] not in ("application/pdf", "image/png"):
        raise DocumentDeliveryError("document_render_failed")
    if result[2] == "image/png":
        # Only an EMAIL-ONLY source (the holder's card as PNG images) may attach an image.
        if source.media_field is not None or not _valid_png(*result[:2]):
            raise DocumentDeliveryError("document_render_failed")
        authorized_attachment(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
        return result
    try:
        validate_document(result[0], result[1])
    except ProviderFailure:
        code = "document_size_exceeded" if isinstance(result[1], bytes) and len(result[1]) > 5 * 1024 * 1024 else "document_render_failed"
        raise DocumentDeliveryError(code) from None
    # Rendering/storage can take time. Recheck revocation before releasing bytes.
    authorized_attachment(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    return result
