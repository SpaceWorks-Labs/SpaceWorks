"""Build approved template parameters from explicitly bound safe-context keys."""
import re

from django.db import transaction

from apps.accounts import rbac
from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, WhatsAppTemplate
from .notification_wa_meta_http import credentials, failure, graph
from .notification_cutover import guarded


DOCUMENT_HEADER = "__document_header__"


def template_content(binding, context, *, media_id=None, filename=None):
    if (binding is None or not binding.approved or binding.needs_review or not isinstance(context, dict)
            or not re.fullmatch(r"[a-z0-9_]{1,255}", binding.template_name)
            or not re.fullmatch(r"[a-z]{2,3}(?:_[A-Z]{2})?", binding.locale)
            or not isinstance(binding.variables, list) or len(binding.variables) > 30):
        return None
    parameters = []
    header = DOCUMENT_HEADER in binding.variables
    if header and (binding.variables[0] != DOCUMENT_HEADER or binding.variables.count(DOCUMENT_HEADER) != 1
            or not isinstance(media_id, str) or not re.fullmatch(r"[0-9]{1,64}", media_id)
            or not isinstance(filename, str)):
        return None
    for key in binding.variables:
        if key == DOCUMENT_HEADER:
            continue
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]{0,63}", key):
            return None
        value = context.get(key)
        if type(value) not in (str, int, float) or not str(value) or len(str(value)) > 1024:
            return None
        parameters.append({"type": "text", "text": str(value)})
    template = {"name": binding.template_name, "language": {"code": binding.locale}}
    components = []
    if header:
        components.append({"type": "header", "parameters": [{"type": "document",
            "document": {"id": media_id, "filename": filename}}]})
    if parameters:
        components.append({"type": "body", "parameters": parameters})
    if components:
        template["components"] = components
    return {"type": "template", "template": template}


def document_header_approved(binding, provider_template):
    components = provider_template.get("components", [])
    if not isinstance(components, list) or provider_template.get("parameter_format", "POSITIONAL") != "POSITIONAL":
        return False
    bodies = [part for part in components if isinstance(part, dict) and part.get("type") == "BODY"]
    variables = [v for v in binding.variables if v != DOCUMENT_HEADER]
    if len(bodies) != 1 or not isinstance(bodies[0].get("text"), str):
        return False
    if re.findall(r"\{\{\s*(.*?)\s*\}\}", bodies[0]["text"]) != [str(i) for i in range(1, len(variables) + 1)]:
        return False
    if any(not isinstance(part, dict) or part.get("type") not in {"BODY", "HEADER"} for part in components):
        return False
    headers = [part for part in components if isinstance(part, dict) and part.get("type") == "HEADER"]
    document = DOCUMENT_HEADER in binding.variables
    if binding.feature and not document and len(components) != 1:
        return False
    if document:
        return (binding.variables[0] == DOCUMENT_HEADER and binding.variables.count(DOCUMENT_HEADER) == 1
            and len(headers) == 1 and headers[0].get("format") == "DOCUMENT")
    # A text binding cannot silently acquire a required media header.
    return not headers and len(components) == 1


def bound_template(configuration, event, audience, locale="en"):
    return rbac.scope_notification_policy(WhatsAppTemplate.objects.all(),
        makerspace_id=configuration.makerspace_id, field="configuration__makerspace_id").filter(configuration=configuration,
        event=event, audience=audience, locale=locale, approved=True, needs_review=False).first()


@guarded(mutation=True)
def sync_templates(configuration):
    """Explicit diagnostics refresh Meta approval; browser writes cannot self-approve.

    Follow cursors only on our fixed Graph host, never a provider-supplied next URL.
    Stop after ten pages and fail closed without partially approving bindings.
    """
    values = credentials(configuration)
    if not values:
        return failure("not_configured")
    approved, cursor = {}, None
    for _ in range(10):
        params = {"fields": "name,language,status,components,parameter_format", "limit": 100}
        if cursor:
            params["after"] = cursor
        result, data = graph(configuration, "GET", f"{values['business_account_id']}/message_templates", params=params)
        if not result.accepted:
            return result
        rows = data.get("data")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            return failure("provider_error")
        approved.update(((row.get("name"), row.get("language")), row) for row in rows
                        if row.get("status") == "APPROVED"
                        and isinstance(row.get("name"), str) and isinstance(row.get("language"), str))
        paging = data.get("paging", {})
        if not isinstance(paging, dict):
            return failure("provider_error")
        if not paging.get("next"):
            break
        cursors = paging.get("cursors", {})
        cursor = cursors.get("after") if isinstance(cursors, dict) else None
        if not isinstance(cursor, str) or not 0 < len(cursor) <= 2048:
            return failure("provider_error")
    else:
        return failure("provider_error")
    with tenant_write(configuration.makerspace_id), transaction.atomic():
        config = rbac.scope_notification_policy(ChannelConfiguration.objects.select_for_update(),
            makerspace_id=configuration.makerspace_id).get(pk=configuration.pk)
        if config.generation != configuration.generation or config.provider != "meta":
            return failure("not_configured")
        changed = 0
        for binding in config.templates.select_for_update():
            provider_template = approved.get((binding.template_name, binding.locale))
            is_approved = bool(provider_template and document_header_approved(binding, provider_template)
                and binding.provider_identity in {"", config.integration_identity})
            if binding.approved != is_approved or (is_approved and binding.needs_review):
                binding.approved = is_approved
                binding.needs_review = not is_approved
                binding.provider_identity = config.integration_identity
                binding.validation_schema = {"body": binding.variables}
                binding.save(update_fields=["approved", "needs_review", "provider_identity", "validation_schema"])
                changed += 1
        if changed:
            audit.record(None, "notification.channel_configured", makerspace=config.makerspace,
                target=config, meta={"channel": "whatsapp", "generation": config.generation,
                                     "fields": ["template_approval"], "changed": changed})
    return result
