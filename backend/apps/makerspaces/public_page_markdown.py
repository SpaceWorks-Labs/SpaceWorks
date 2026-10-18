"""Bounded restricted Markdown and URL validation; no network or model dependencies."""

import html
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from rest_framework.exceptions import ValidationError

TAG = re.compile(r"<\s*/?\s*[A-Za-z!][^>]*(?:>|$)")


def public_url(value, *, legacy_http=False, allow_blank=True):
    if value == "" and allow_blank:
        return value
    if not isinstance(value, str) or len(value) > 500:
        raise ValidationError("Use a URL of at most 500 characters.")
    decoded = value
    for _ in range(3):
        decoded = html.unescape(unquote(decoded))
    if any(unicodedata.category(c).startswith("C") or c.isspace() for c in decoded):
        raise ValidationError("URLs cannot contain whitespace or control characters.")
    try:
        parsed = urlsplit(value)
        decoded_url = urlsplit(decoded)
        schemes = {"https", "http"} if legacy_http else {"https"}
        if (parsed.scheme.lower() not in schemes or decoded_url.scheme.lower() not in schemes
                or not parsed.hostname or not decoded_url.hostname or parsed.username is not None
                or parsed.password is not None or decoded_url.username is not None
                or decoded_url.password is not None or "\\" in decoded):
            raise ValueError
        parsed.port
    except ValueError as exc:
        raise ValidationError("Use an absolute HTTPS URL without credentials.") from exc
    return value


def links(text):
    """Read balanced inline targets in linear time, including nested URL parentheses.

    Incomplete constructs stay literal, matching RestrictedMarkdown. Escaped brackets
    are literal too. Complete image constructs are prohibited by the caller.
    """
    index = 0
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] != "[":
            index += 1
            continue
        start = index
        index += 1
        while index < len(text) and text[index] not in "]\n":
            index += 2 if text[index] == "\\" else 1
        if index >= len(text) or text[index:index + 2] != "](":
            index += 1
            continue
        target_start = index + 2
        index = target_start
        depth = 1
        while index < len(text) and depth and text[index] != "\n":
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
            index += 1
        if depth == 0:
            yield start, index, text[target_start:index - 1]


def validate_markdown(value, *, legacy_http=False, limit=10000):
    if not isinstance(value, str):
        raise ValidationError("Expected text.")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if any(unicodedata.category(c) == "Cs" for c in value):
        raise ValidationError("Text contains unsupported surrogate characters.")
    if len(value) > limit or len(value.encode("utf-8")) > 131072:
        raise ValidationError("Text exceeds the allowed length.")
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in value):
        raise ValidationError("Text contains control characters.")
    if TAG.search(value) or re.search(r"!\s*\[", value):
        raise ValidationError("HTML, embeds and Markdown images are not supported.")
    for _, _, url in links(value):
        public_url(url, legacy_http=legacy_http, allow_blank=False)
    return value


def rendering_policy(value):
    """Only backfill/unchanged legacy text may use escaped literal presentation."""
    try:
        validate_markdown(value, legacy_http=True)
    except ValidationError:
        return "legacy_literal_v1"
    return "restricted_v1"


def excerpt(value, *, limit=300):
    # Metadata is plain text, never an HTML fragment. The share renderer escapes it.
    return " ".join(str(value).split())[:limit]


def plain_excerpt(markdown, *, limit=300):
    """Share/metadata text from restricted Markdown: link labels kept, markup dropped."""
    text, parts, cursor = str(markdown), [], 0
    for start, end, url in links(text):
        parts += [text[cursor:start], text[start + 1:end - len(url) - 3]]
        cursor = end
    parts.append(text[cursor:])
    text = re.sub(r"(?m)^[ \t]*(?:#{1,6}|>|[-+*]|\d+\.)[ \t]+", "", "".join(parts))
    return excerpt(re.sub(r"\\(.)|[*`]", r"\1", text), limit=limit)


def document_description(document):
    """The first enabled About section summarizes a page that has no description field."""
    for section in document["sections"]:
        if section["enabled"] and section["type"] == "about":
            text = plain_excerpt(section["payload"].get("markdown", ""))
            if text:
                return text
    return ""
