"""Build approved template parameters from explicitly bound safe-context keys."""
import re

from django.db import transaction

from apps.accounts import rbac
from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, WhatsAppTemplate
from .notification_wa_meta_http import credentials, failure, graph


def template_content(binding, context):
    if (binding is None or not binding.approved or not isinstance(context, dict)
            or not re.fullmatch(r"[a-z0-9_]{1,255}", binding.template_name)
            or not re.fullmatch(r"[a-z]{2,3}(?:_[A-Z]{2})?", binding.locale)
            or not isinstance(binding.variables, list) or len(binding.variables) > 30):
        return None
    parameters = []
    for key in binding.variables:
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key):
            return None
        value = context.get(key)
        if type(value) not in (str, int, float) or not str(value) or len(str(value)) > 1024:
            return None
        parameters.append({"type": "text", "text": str(value)})
    template = {"name": binding.template_name, "language": {"code": binding.locale}}
    if parameters:
        template["components"] = [{"type": "body", "parameters": parameters}]
    return {"type": "template", "template": template}


def bound_template(configuration, event, audience, locale="en"):
    return rbac.scope_notification_policy(WhatsAppTemplate.objects.all(),
        makerspace_id=configuration.makerspace_id, field="configuration__makerspace_id").filter(configuration=configuration,
        event=event, audience=audience, locale=locale, approved=True).first()


def sync_templates(configuration):
    """Explicit diagnostics refresh Meta approval; browser writes cannot self-approve.

    Follow cursors only on our fixed Graph host, never a provider-supplied next URL.
    Stop after ten pages and fail closed without partially approving bindings.
    """
    values = credentials(configuration)
    if not values:
        return failure("not_configured")
    approved, cursor = set(), None
    for _ in range(10):
        params = {"fields": "name,language,status", "limit": 100}
        if cursor:
            params["after"] = cursor
        result, data = graph(configuration, "GET", f"{values['business_account_id']}/message_templates", params=params)
        if not result.accepted:
            return result
        rows = data.get("data")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            return failure("provider_error")
        approved.update((row.get("name"), row.get("language")) for row in rows
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
            is_approved = (binding.template_name, binding.locale) in approved
            if binding.approved != is_approved:
                binding.approved = is_approved
                binding.save(update_fields=["approved"])
                changed += 1
        if changed:
            audit.record(None, "notification.channel_configured", makerspace=config.makerspace,
                target=config, meta={"channel": "whatsapp", "generation": config.generation,
                                     "fields": ["template_approval"], "changed": changed})
    return result
