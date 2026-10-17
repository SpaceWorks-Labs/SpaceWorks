"""Meta Cloud API approved template sends, positional text-only BODY parameters."""
import json
import re
from urllib.parse import quote
from urllib.request import Request

from django.conf import settings

from .transport import SendResult, send_request


def send_message(sender, *, to, template_name, language, parameters, delivery_id):
    version = settings.WHATSAPP_GRAPH_VERSION
    if not re.fullmatch(r"v\d+\.\d+", version):
        return SendResult(error_code="invalid_graph_version", permanent=True)
    if not isinstance(parameters, (list, tuple)) or any(not isinstance(value, str) for value in parameters):
        return SendResult(error_code="invalid_template_parameters", permanent=True)
    template = {"name": template_name, "language": {"code": language}}
    if parameters:
        template["components"] = [{"type": "body", "parameters": [
            {"type": "text", "text": value} for value in parameters
        ]}]
    payload = {"messaging_product": "whatsapp", "to": to, "type": "template", "template": template,
               "biz_opaque_callback_data": str(delivery_id)}
    req = Request(f"https://graph.facebook.com/{version}/{quote(sender.phone_number_id, safe='')}/messages",
                  data=json.dumps(payload).encode(), method="POST", headers={
                      "Authorization": f"Bearer {sender.access_token}", "Content-Type": "application/json",
                  })
    return send_request(req, provider="meta")
