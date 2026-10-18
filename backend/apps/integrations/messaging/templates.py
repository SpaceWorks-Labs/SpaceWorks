"""Pinned Meta languages and positional BODY-only binding validation."""
from apps.integrations.notification_cutover import guarded
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


def save_binding(actor, space, values, pk=None, *, delete=False):
    from apps.integrations.notification_legacy_api import deny_legacy_write
    deny_legacy_write()
