"""Bounded placeholders use the existing Django email renderer, with data-only context."""

import re
from rest_framework.exceptions import ValidationError
from .email_templates import _render_strings


def validate_strings(subject, body, allowed):
    if not subject.strip() or len(subject) > 200 or "\n" in subject or "\r" in subject:
        raise ValidationError({"subject": "Use a subject of 1-200 characters on one line."})
    if not body.strip() or len(body) > 10000:
        raise ValidationError({"body": "Use a message of 1-10000 characters."})
    for value in (subject, body):
        tokens = re.findall(r"{{\s*([a-z_]+)\s*}}", value)
        remainder = re.sub(r"{{\s*[a-z_]+\s*}}", "", value)
        if set(tokens) - set(allowed) or any(token in remainder for token in ("{{", "}}", "{%", "%}", "{#", "#}")):
            raise ValidationError({"body": f"Use only these placeholders: {', '.join(allowed)}."})


def render(subject, body, context):
    validate_strings(subject, body, context)
    rendered = _render_strings(subject, body, "", context)
    rendered["subject"] = " ".join(rendered["subject"].splitlines())
    return rendered
