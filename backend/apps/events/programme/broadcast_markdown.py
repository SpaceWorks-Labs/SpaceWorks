"""The safe markdown subset of the broadcast composer: validation, HTML and plain-text projection.

Allowed: paragraphs, line breaks, `**bold**`, `*italic*`, `- ` bullets, `1. ` numbered lists, `# ` headings
(up to three levels), `> ` quotes and `[label](https://...)` / `[label](mailto:...)` links. Raw HTML, images,
reference definitions and every other URL scheme are refused. The HTML is built from escaped text only, so a
body can never inject markup; links are re-checked at render time as defence in depth.
"""

import html
import re
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator, validate_email
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

LINK_PLACEHOLDERS = ("event_url", "ticket_url", "feedback_url", "schedule_url")
LINK_RE = re.compile(r"\[([^\[\]\n]{1,80})\]\((\{\{\s*[a-z_]+\s*\}\}|[^()\s]{1,2048})\)")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
_CREDENTIAL_RE = re.compile(r"(?:token|secret|password|credential|check-?in|invite|presign|signature)")
_QUOTE = "&gt;"
_FORBIDDEN_SOURCE_RE = re.compile(r"<[^>]*>|!\[|^\s*\[[^]]+\]:", flags=re.MULTILINE)


def _link_error():
    return ValidationError({"body": gettext("Links must be https or mailto addresses without credentials.")})


def safe_url(value):
    """The URL when it is a plain public https or mailto target, else None."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    if any(ord(char) < 33 or char in '{}<>\\"' for char in value):
        return None
    if value.startswith("mailto:"):
        address = value[7:]
        try:
            validate_email(address)
        except DjangoValidationError:
            return None
        return value
    try:
        URLValidator(schemes=["https"])(value)
        parsed = urlsplit(value)
    except (DjangoValidationError, ValueError):
        return None
    if parsed.username or parsed.password or _CREDENTIAL_RE.search(unquote(value).casefold()):
        return None
    return value


def validate_markdown(body):
    """Refuse everything outside the subset; returns the body unchanged."""
    if _FORBIDDEN_SOURCE_RE.search(body):
        raise ValidationError({"body": gettext("Use text and emphasis; add links as calls to action.")})
    for match in LINK_RE.finditer(body):
        target = match.group(2)
        placeholder = _PLACEHOLDER_RE.fullmatch(target)
        if placeholder:
            if placeholder.group(1) not in LINK_PLACEHOLDERS:
                raise _link_error()
        elif safe_url(target) is None:
            raise _link_error()
    # Whatever is left after valid links are removed must not look like link syntax.
    if re.search(r"\]\s*\(", LINK_RE.sub("", body)):
        raise _link_error()
    return body


def _inline(escaped):
    stash = []

    def keep(match):
        target = html.unescape(match.group(2))
        url = safe_url(target)
        label = match.group(1)
        if url is None:
            return label
        stash.append('<a rel="noopener noreferrer" href="' + html.escape(url, quote=True) + '">' + label + "</a>")
        return f"\x00{len(stash) - 1}\x00"

    text = LINK_RE.sub(keep, escaped)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)


def _block(paragraph):
    lines = paragraph.splitlines()
    if not lines:
        return ""
    if all(line.startswith("- ") for line in lines):
        return "<ul>" + "".join("<li>" + _inline(line[2:]) + "</li>" for line in lines) + "</ul>"
    if all(re.match(r"\d{1,3}\. ", line) for line in lines):
        return "<ol>" + "".join("<li>" + _inline(re.sub(r"^\d{1,3}\. ", "", line)) + "</li>" for line in lines) + "</ol>"
    if all(line.startswith(_QUOTE) for line in lines):
        inner = "<br>".join(_inline(line[len(_QUOTE):].lstrip()) for line in lines)
        return '<blockquote style="margin:0 0 16px;padding:0 0 0 14px;border-left:3px solid #8a8a8a">' + inner + "</blockquote>"
    heading = re.match(r"(#{1,3}) (.+)$", lines[0]) if len(lines) == 1 else None
    if heading:
        tag = "h2" if len(heading.group(1)) == 1 else "h3"
        return f'<{tag} style="margin:0 0 12px;line-height:1.3">' + _inline(heading.group(2)) + f"</{tag}>"
    return "<p>" + "<br>".join(_inline(line) for line in lines) + "</p>"


def markdown_html(value):
    escaped = html.escape(value)
    return "".join(_block(paragraph) for paragraph in escaped.split("\n\n"))


def plain_text(value):
    """Plain-text projection of the new syntax (headings, links); bullets, quotes and emphasis stay as typed."""
    text = re.sub(r"^#{1,3} ", "", value, flags=re.MULTILINE)
    return LINK_RE.sub(lambda m: f"{m.group(1)} ({m.group(2)})", text)
