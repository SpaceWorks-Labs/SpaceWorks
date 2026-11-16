"""WhatsApp document attempts preserve template and provider callback identity rules."""
from .notification_document_transport import personal_destination, validate_document
from .notification_providers import ProviderResult
from .notification_slack_http import failure_result
from .notification_wa_window import in_session_window


def meta_document(provider, delivery, *, filename, pdf_bytes, caption):
    def send():
        from .notification_wa_meta_http import credentials, failure, graph, send_message, ID
        from .notification_wa_meta_reference import client_reference
        from .notification_wa_meta_templates import DOCUMENT_HEADER, bound_template, sync_templates, template_content
        config, endpoint, envelope = provider.configuration, delivery.endpoint, delivery.envelope
        personal_destination(config, delivery)
        validate_document(filename, pdf_bytes)
        if not provider._live_target(endpoint):
            return failure("invalid_endpoint")
        binding = None
        if not in_session_window(endpoint):
            approval = sync_templates(config)
            if not approval.accepted:
                return approval
            binding = bound_template(config, envelope.event + ".document", envelope.audience,
                                     envelope.context.get("locale", "en"))
            if binding is None or DOCUMENT_HEADER not in binding.variables:
                return failure("unsupported")
        # Template approval performs external I/O: withdrawal or rotation wins
        # before the private bytes are uploaded, as well as before sharing.
        personal_destination(config, delivery)
        if not provider._live_target(endpoint):
            return failure("invalid_endpoint")
        values = credentials(config)
        result, upload = graph(config, "POST", f"{values['phone_number_id']}/media",
            files={"file": (filename, pdf_bytes, "application/pdf")},
            form={"messaging_product": "whatsapp", "type": "application/pdf"})
        if not result.accepted:
            return result
        media_id = upload.get("id")
        if not isinstance(media_id, str) or not ID.fullmatch(media_id):
            return failure("provider_error", retryable=True)
        if not provider._live_target(endpoint):
            return failure("invalid_endpoint")
        if binding:
            content = template_content(binding, envelope.context, media_id=media_id, filename=filename)
            if content is None:
                return failure("unsupported")
        elif in_session_window(endpoint):
            content = {"type": "document", "document": {"id": media_id,
                "filename": filename, "caption": str(caption)[:1024]}}
        else:
            # The window can close during upload; text fallback uses its own template.
            return failure("unsupported")
        content["biz_opaque_callback_data"] = client_reference(config, delivery)
        return send_message(config, endpoint.destination, content)
    return failure_result("whatsapp", send)


def twilio_document(provider, delivery, *, filename, pdf_bytes, caption):
    def send():
        from .notification_media import issue_grant
        from .notification_wa_twilio_templates import template_payload
        config, endpoint, envelope = provider.configuration, delivery.endpoint, delivery.envelope
        personal_destination(config, delivery)
        validate_document(filename, pdf_bytes)
        if not provider.active() or not provider.valid_endpoint(endpoint):
            return ProviderResult(False, error_code="invalid_endpoint")
        context = envelope.context
        # A placeholder determines binding availability without issuing a bearer yet.
        payload = None
        if not in_session_window(endpoint):
            payload = template_payload(config, envelope.event + ".document", envelope.audience,
                context.get("locale", "en"), context, document_url="placeholder.pdf")
            if payload is None:
                return ProviderResult(False, error_code="unsupported")
        grant_url = issue_grant(delivery)
        credentials = provider.credentials()
        if not grant_url.startswith(credentials.public_base_url + "/"):
            return ProviderResult(False, error_code="not_configured")
        if payload:
            payload = template_payload(config, envelope.event + ".document", envelope.audience,
                context.get("locale", "en"), context,
                document_url=grant_url[len(credentials.public_base_url) + 1:])
            if payload is None:
                return ProviderResult(False, error_code="unsupported")
        elif in_session_window(endpoint):
            payload = {"MediaUrl": grant_url, "Body": str(caption)[:1024]}
        else:
            return ProviderResult(False, error_code="unsupported")
        personal_destination(config, delivery)
        if not provider.active() or not provider.valid_endpoint(endpoint):
            return ProviderResult(False, error_code="invalid_endpoint")
        return provider._send(endpoint.destination, payload, delivery.pk)
    return failure_result("whatsapp", send)
