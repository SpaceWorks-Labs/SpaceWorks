"""A same-origin relative `next` path for the social sign-in start (0.12.0).

Only an absolute-path reference is accepted ("/members/loans?tab=open"): no scheme, host,
protocol-relative `//`, backslash, control character or fragment-smuggling form, so the value
echoed back by the callback can never become an open redirect.
"""
from urllib.parse import unquote, urlsplit

from django.utils.translation import gettext
from rest_framework import serializers

MAX_NEXT_LENGTH = 512


def validate_next_path(value):
    value = (value or "").strip()
    if not value:
        return ""
    decoded = unquote(value)
    parsed = urlsplit(value)
    bad = (
        len(value) > MAX_NEXT_LENGTH
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value or "\\" in decoded
        or decoded.startswith("//")
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in decoded)
        or parsed.scheme or parsed.netloc
    )
    if bad:
        raise serializers.ValidationError(gettext("Use a path on this site, such as /dashboard."))
    return value


class NextPathField(serializers.CharField):
    """Optional `next`, stored as `next_path` so the Python keyword-ish name never leaks."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_blank", True)
        kwargs.setdefault("max_length", MAX_NEXT_LENGTH)
        kwargs.setdefault("source", "next_path")
        kwargs.setdefault("help_text", "Optional same-origin relative path the callback returns after sign-in.")
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        return validate_next_path(super().to_internal_value(data))
