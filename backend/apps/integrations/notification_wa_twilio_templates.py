"""Approved Twilio Content SIDs and bounded variables from the safe context only."""
import json
import math

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, WhatsAppTemplate
from .notification_wa_twilio_config import sid
from .notification_wa_twilio_http import CONTENT_ROOT, call


def template_payload(config, event, audience, locale, context):
    binding = WhatsAppTemplate.objects.filter(configuration=config, event=event,
        audience=audience, locale=locale, approved=True).first()
    if binding is None or not sid(binding.template_name, "HX"):
        return None
    names = binding.variables
    if not isinstance(names, list) or len(names) > 30 or len(set(names)) != len(names):
        return None
    values = {}
    for index, name in enumerate(names, 1):
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
    results, approvals, unavailable = {}, {}, 0
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
                approved=results[binding.pk]).update(approved=results[binding.pk])
        audit.record(actor, "notification.whatsapp_templates_refreshed", makerspace=current.makerspace,
            target=current, meta={"changed": changed, "unavailable": unavailable})
    return {"checked": len(bindings), "approved": sum(results.values()), "unavailable": unavailable}
