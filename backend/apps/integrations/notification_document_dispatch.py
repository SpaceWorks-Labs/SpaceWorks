"""Document attempts share the envelope's quota, claim and retry budget."""
from .notification_attachment_sources import (
    DocumentDeliveryError, attachment_references, render_attachment,
    attachment_source_boundary,
)
from .notification_providers import ProviderResult


def send_document(provider, delivery, rendered):
    try:
        references = attachment_references(delivery.envelope)
        if not references:
            return provider.send(delivery, rendered)
        with attachment_source_boundary(references[0], makerspace_id=delivery.makerspace_id,
                recipient_id=delivery.envelope.recipient_id):
            return _send_attachment(provider, delivery, rendered, references[0])
    except DocumentDeliveryError as exc:
        return ProviderResult(False, retryable=True, error_code=str(exc))


def _send_attachment(provider, delivery, rendered, reference):
    filename, pdf, _ = render_attachment(reference, makerspace_id=delivery.makerspace_id,
        recipient_id=delivery.envelope.recipient_id)
    send = getattr(provider, "send_document", None)
    result = (send(delivery, filename=filename, pdf_bytes=pdf, caption=rendered.get("text", ""))
              if send else ProviderResult(False, error_code="unsupported"))
    # A timeout can mean the provider already sent the PDF. Sending text here
    # would duplicate the notice and hide the uncertain upload in delivery health.
    if not result.accepted and not result.retryable and not result.ambiguous:
        return provider.send(delivery, rendered)
    return result
