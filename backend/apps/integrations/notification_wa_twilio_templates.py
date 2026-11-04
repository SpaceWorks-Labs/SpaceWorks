"""Approved Twilio Content SIDs and bounded variables from the safe context only."""
import json
import math
import re

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, WhatsAppTemplate
from .notification_wa_twilio_config import sid
from .notification_wa_twilio_http import CONTENT_ROOT, call
from .notification_cutover import guarded

DOCUMENT_MEDIA = "__document_media__"


def template_payload(config, event, audience, locale, context, *, document_url=None):
    binding = WhatsAppTemplate.objects.filter(configuration=config, event=event,
        audience=audience, locale=locale, approved=True, needs_review=False).first()
    if binding is None or not sid(binding.template_name, "HX"):
        return None
    names = binding.variables
    if not isinstance(names, list) or len(names) > 30 or len(set(names)) != len(names):
        return None
    if (DOCUMENT_MEDIA in names) != (document_url is not None):
        return None
    values = {}
    for index, name in enumerate(names, 1):
        if name == DOCUMENT_MEDIA:
            if (not isinstance(document_url, str) or document_url.startswith("/")
                    or ":" in document_url or not document_url.endswith(".pdf")
                    or len(document_url) > 1024):
                return None
            values[str(index)] = document_url
            continue
        if not isinstance(name, str) or name not in context:
            return None
        value = context[name]
        if not isinstance(value, (str, int, float, bool)) or (isinstance(value, float) and not math.isfinite(value)):
            return None
        value = str(value)
        if not value.strip() or len(value) > 1024:
            return None
        values[str(index)] = value
    return {"ContentSid": binding.template_name, "ContentVariables": json.dumps(values, ensure_ascii=False)}


def approved_document_content(config, credentials, binding, content):
    """Twilio media variables are paths after a static origin, never a variable host."""
    if (not isinstance(content, dict) or content.get("account_sid") != credentials.account_sid
            or content.get("sid") != binding.template_name or content.get("language") != binding.locale
            or not isinstance(binding.variables, list)
            or binding.variables.count(DOCUMENT_MEDIA) != 1):
        return False
    index = str(binding.variables.index(DOCUMENT_MEDIA) + 1)
    types, samples = content.get("types"), content.get("variables")
    media = types.get("twilio/media") if isinstance(types, dict) else None
    sample = samples.get(index) if isinstance(samples, dict) else None
    return bool(isinstance(media, dict)
        and media.get("media") == [credentials.public_base_url + "/{{" + index + "}}"]
        and isinstance(sample, str) and not sample.startswith("/") and ":" not in sample
        and sample.lower().endswith(".pdf") and "{{" + index + "}}" not in str(media.get("body", "")))


def approved_text_content(credentials, binding, content):
    if (not isinstance(content, dict) or content.get("account_sid") != credentials.account_sid
            or content.get("sid") != binding.template_name or content.get("language") != binding.locale):
        return False
    types = content.get("types")
    if not isinstance(types, dict) or set(types) != {"twilio/text"}:
        return False
    text = types["twilio/text"]
    body = text.get("body") if isinstance(text, dict) else None
    samples = content.get("variables") or {}
    positions = [str(index) for index in range(1, len(binding.variables) + 1)]
    return (isinstance(body, str) and isinstance(samples, dict) and set(samples) == set(positions)
        and re.findall(r"\{\{\s*(.*?)\s*\}\}", body) == positions)


@guarded(mutation=True)
def refresh_approvals(config, credentials, actor, *, content_sids=None):
    """Do provider I/O without locks, then reject a concurrent installation rotation."""
    generation, identity = config.generation, config.integration_identity
    rows = WhatsAppTemplate.objects.filter(configuration=config)
    if content_sids is not None:
        rows = rows.filter(template_name__in=content_sids)
    bindings = list(rows.order_by("pk")[:101])
    if len(bindings) > 100:
        raise ValidationError({"templates": "At most 100 template bindings."})
    if len({b.template_name for b in bindings if sid(b.template_name, "HX")}) > 5:
        raise ValidationError({"content_sids": "Select at most five Content SIDs per refresh."})
    results, approvals, contents, unavailable = {}, {}, {}, 0
    for binding in bindings:
        approved = False
        if sid(binding.template_name, "HX"):
            if binding.template_name not in approvals:
                approvals[binding.template_name] = call(credentials, f"{CONTENT_ROOT}/{binding.template_name}/ApprovalRequests")
            data, error = approvals[binding.template_name]
            if error:
                unavailable += 1
            else:
                whatsapp = data.get("whatsapp")
                approved = (data.get("account_sid") == credentials.account_sid
                    and data.get("sid") == binding.template_name and isinstance(whatsapp, dict)
                    and whatsapp.get("status") == "approved")
                if approved:
                    if binding.template_name not in contents:
                        contents[binding.template_name] = call(credentials, f"{CONTENT_ROOT}/{binding.template_name}")
                    content, content_error = contents[binding.template_name]
                    if content_error:
                        unavailable += 1
                    approved = not content_error and (approved_document_content(config, credentials, binding, content)
                        if DOCUMENT_MEDIA in binding.variables else approved_text_content(credentials, binding, content))
        results[binding.pk] = approved
    with tenant_write(config.makerspace_id), transaction.atomic():
        current = rbac.scope_notification_policy(ChannelConfiguration.objects.select_for_update(),
            makerspace_id=config.makerspace_id).get(pk=config.pk)
        if (current.generation != generation or current.integration_identity != identity
                or current.provider != "twilio"):
            raise ValidationError({"channel": "Integration changed; refresh again."})
        changed = 0
        for binding in bindings:
            # A concurrent settings edit may have replaced the bindings entirely.
            changed += WhatsAppTemplate.objects.filter(pk=binding.pk, configuration=current,
                template_name=binding.template_name, variables=binding.variables).exclude(
                approved=results[binding.pk], needs_review=not results[binding.pk]).update(
                    approved=results[binding.pk], needs_review=not results[binding.pk],
                    provider_identity=current.integration_identity, validation_schema={"body": binding.variables})
        audit.record(actor, "notification.whatsapp_templates_refreshed", makerspace=current.makerspace,
            target=current, meta={"changed": changed, "unavailable": unavailable})
    return {"checked": len(bindings), "approved": sum(results.values()), "unavailable": unavailable}
