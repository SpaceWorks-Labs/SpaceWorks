"""Pinned Meta languages and positional BODY-only binding validation."""
import re

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.audit.services import record
from apps.integrations.models import MakerspaceMessagingSettings, WhatsAppTemplateBinding
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import tenant_write
from .projections import PROJECTION_KEYS

# Meta template language codes. Values are deliberately pinned, never inferred from locales.
WHATSAPP_LANGUAGES = tuple("af sq ar az bn bg ca zh_CN zh_HK zh_TW hr cs da nl en en_GB en_US et fil fi fr fr_CA fr_CH ka de el gu ha he hi hu id ga it ja kn kk rw ko ky lo lv lt mk ms ml mr nb fa pl pt_BR pt_PT pa ro ru sr sk sl es es_AR es_ES es_MX sw sv ta te th tr uk ur uz vi zu".split())


def validate_binding(values, instance=None):
    def field(name, default=None):
        return values.get(name, getattr(instance, name, default))
    key = (field("feature"), field("event"), field("audience"))
    allowed = PROJECTION_KEYS.get(key)
    if allowed is None:
        raise ValidationError({"event": "No reviewed projection for this feature, event and audience."})
    if field("language") not in WHATSAPP_LANGUAGES:
        raise ValidationError({"language": "Unsupported Meta template language code."})
    if not re.fullmatch(r"[a-z0-9_]{1,512}", field("template_name") or ""):
        raise ValidationError({"template_name": "Use Meta's lowercase template name."})
    parameters = field("parameters", [])
    if not isinstance(parameters, list) or len(parameters) > 100 or any(
        not isinstance(key, str) or key not in allowed for key in parameters
    ):
        raise ValidationError({"parameters": "Only ordered, reviewed BODY text projection keys are supported."})
    # Provider component metadata, when supplied, is a validation assertion only.
    components = values.pop("components", [])
    if not isinstance(components, list) or len(components) > 1:
        raise ValidationError({"components": "Only one positional BODY component is supported."})
    for component in components:
        if not isinstance(component, dict) or set(component) - {"type", "text", "parameter_format"}:
            raise ValidationError({"components": "Media, buttons and named parameters are unsupported."})
        text = component.get("text", "")
        if (str(component.get("type", "")).upper() != "BODY" or component.get("parameter_format", "POSITIONAL") != "POSITIONAL"
            or not isinstance(text, str)):
            raise ValidationError({"components": "Only positional BODY text is supported."})
        placeholders = re.findall(r"\{\{\s*(.*?)\s*\}\}", text)
        if placeholders != [str(index) for index in range(1, len(parameters) + 1)]:
            raise ValidationError({"components": "BODY parameters must be numbered consecutively from 1."})
    return values


def binding_for(makerspace, sender, feature, event, audience):
    owner = makerspace if sender.provider_source == "own" else None
    return WhatsAppTemplateBinding.objects.filter(makerspace=owner, business_account_id=sender.business_account_id,
        feature=feature, event=event, audience=audience, is_active=True, needs_review=False).first()


@transaction.atomic
def save_binding(actor, space, values, pk=None, *, delete=False):
    with tenant_write(space.pk):
        space = Makerspace.objects.select_for_update().get(pk=space.pk)
        if not rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, space.pk):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        row = get_object_or_404(WhatsAppTemplateBinding, makerspace=space, pk=pk) if pk else WhatsAppTemplateBinding(makerspace=space)
        if delete:
            record(actor, "messaging.template_deleted", makerspace=space, target=row, meta={"fields": []})
            row.delete()
            return None
        validate_binding(values, row)
        own = MakerspaceMessagingSettings.objects.filter(makerspace=space).first()
        if not own or not own.whatsapp_business_account_id:
            raise ValidationError({"business_account_id": "Configure your own WhatsApp business account first; platform bindings are managed by the operator."})
        for key, value in values.items():
            setattr(row, key, value)
        row.business_account_id = own.whatsapp_business_account_id
        from .templates_provider import validate_provider_template
        from .settings_service import read_secret
        validate_provider_template(business_account_id=row.business_account_id, access_token=read_secret(own, "whatsapp_access_token"),
                                   template_name=row.template_name, language=row.language, parameters=row.parameters)
        row.needs_review = False
        row.save()
        record(actor, "messaging.template_saved", makerspace=space, target=row, meta={"fields": sorted(values)})
        return row
