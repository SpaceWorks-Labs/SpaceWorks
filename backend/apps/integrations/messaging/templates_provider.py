"""Check authoritative Meta template shape before accepting a binding."""
import json
import re
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError


class TemplateCheckUnavailable(APIException):
    status_code = 503
    default_detail = {"code": "template_check_unavailable", "detail": "Meta template approval could not be verified. Try again."}


def validate_provider_template(*, business_account_id, access_token, template_name, language, parameters):
    if not access_token:
        raise ValidationError({"template_name": "Configure an access token with template-management permission first."})
    if not re.fullmatch(r"v\d+\.\d+", settings.WHATSAPP_GRAPH_VERSION):
        raise TemplateCheckUnavailable()
    query = urlencode({"name": template_name, "fields": "name,language,status,components,parameter_format", "limit": 100})
    req = Request(f"https://graph.facebook.com/{settings.WHATSAPP_GRAPH_VERSION}/{quote(business_account_id, safe='')}/message_templates?{query}",
                  headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read(1024 * 1024))
        templates = data.get("data", [])
        selected = next((row for row in templates if row.get("name") == template_name and row.get("language") == language), None)
    except Exception:
        # Neither Graph bodies (which may echo credentials) nor raw exception text escapes.
        raise TemplateCheckUnavailable() from None
    if not selected or selected.get("status") != "APPROVED":
        raise ValidationError({"template_name": "An approved template with this name and language is required."})
    if selected.get("parameter_format", "POSITIONAL") != "POSITIONAL":
        raise ValidationError({"parameters": "Named template parameters are unsupported."})
    components = selected.get("components", [])
    if not isinstance(components, list) or len(components) != 1:
        raise ValidationError({"template_name": "Only one text BODY component is supported."})
    body = components[0]
    if not isinstance(body, dict) or body.get("type") != "BODY" or not isinstance(body.get("text"), str):
        raise ValidationError({"template_name": "Headers, media and buttons are unsupported."})
    placeholders = re.findall(r"\{\{\s*(.*?)\s*\}\}", body["text"])
    if placeholders != [str(index) for index in range(1, len(parameters) + 1)]:
        raise ValidationError({"parameters": "The approved BODY must use consecutive positional parameters matching the binding."})
