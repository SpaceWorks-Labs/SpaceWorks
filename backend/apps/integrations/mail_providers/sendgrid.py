"""Narrow SendGrid v3 mail transport; independent of the unsupported Anymail adapter."""

import base64
from email.utils import parseaddr

import requests
from django.core.mail.backends.base import BaseEmailBackend


class ProviderRejected(Exception):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__("email_provider_rejected")


def address(value):
    name, email = parseaddr(value)
    return {"email": email, **({"name": name} if name else {})}


def payload(message):
    # Build/validate Django's MIME message first (header injection and address checks).
    message.message()
    personal = {key: [address(v) for v in getattr(message, key)]
                for key in ("to", "cc", "bcc") if getattr(message, key)}
    result = {"from": address(message.from_email), "personalizations": [personal],
              "subject": message.subject, "content": [{"type": "text/plain", "value": message.body}]}
    for alternative in getattr(message, "alternatives", ()):
        if alternative.mimetype != "text/html":
            raise ValueError("Unsupported mail alternative.")
        result["content"].append({"type": "text/html", "value": alternative.content})
    if message.reply_to:
        result["reply_to_list"] = [address(v) for v in message.reply_to]
    if message.extra_headers:
        result["headers"] = dict(message.extra_headers)
    attachments = []
    for attachment in message.attachments:
        if not hasattr(attachment, "filename"):
            raise ValueError("Unsupported MIME attachment.")
        content = attachment.content
        content = content.encode("utf-8") if isinstance(content, str) else content
        attachments.append({"filename": attachment.filename or "attachment",
                            "type": attachment.mimetype, "disposition": "attachment",
                            "content": base64.b64encode(content).decode("ascii")})
    if attachments:
        result["attachments"] = attachments
    return result


class EmailBackend(BaseEmailBackend):
    def __init__(self, *, api_key, timeout=10, **kwargs):
        super().__init__(**kwargs)
        self.api_key, self.timeout = api_key, timeout

    def send_messages(self, email_messages):
        count = 0
        with requests.Session() as session:
            for message in email_messages:
                if not message.recipients():
                    continue
                response = session.post(
                    "https://api.sendgrid.com/v3/mail/send", json=payload(message),
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=(self.timeout / 2, self.timeout / 2), allow_redirects=False)
                if response.status_code != 202:
                    raise ProviderRejected(response.status_code)
                message.spaceworks_provider_message_id = response.headers.get("X-Message-Id", "")[:200]
                count += 1
        return count
