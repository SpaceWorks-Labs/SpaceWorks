"""Data-only composer payloads; never evaluate markup or caller-supplied HTML."""

from django.utils.translation import gettext
import html
import json
import re
from urllib.parse import unquote, urlsplit

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from apps.integrations.broadcasts_templates import render, validate_strings

from .broadcast_designs import DESIGNS

PLACEHOLDERS = ("name", "event_title", "event_date", "event_location", "ticket_url",
                "event_url", "feedback_url", "schedule_url", "organization")
NAVIGATION_TARGETS = ("event", "ticket")
GILROY_FACES = ((400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold"))


def font_faces(*, preview):
    # srcDoc resolves these fixed root paths against the app document. Mail may
    # use its configured frontend origin; content/CTA URLs never select fonts.
    origin = ""
    if not preview:
        from django.conf import settings
        configured = settings.PUBLIC_APP_BASE_URL
        try:
            parsed = urlsplit(configured)
            if (parsed.scheme in {"https", "http"} and parsed.hostname and parsed.port != 0
                    and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                    and not any(ord(char) < 33 or char in '\"\'<>\\{}' for char in configured)):
                origin = f"{parsed.scheme}://{parsed.netloc}"
        except (TypeError, ValueError):
            pass
    return "".join('@font-face{font-family:"Gilroy";src:url("' + origin + '/fonts/Gilroy-' + face
        + '.woff2") format("woff2");font-style:normal;font-weight:' + str(weight)
        + ';font-display:swap;}' for weight, face in GILROY_FACES)


def validate_ctas(ctas):
    if not isinstance(ctas, list) or len(ctas) > 3:
        raise ValidationError({"ctas": gettext("Use at most three calls to action.")})
    result = []
    for item in ctas:
        if not isinstance(item, dict):
            raise ValidationError({"ctas": gettext("Each call to action must be an object.")})
        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in {"https", "navigation"}:
            raise ValidationError({"ctas": gettext("Choose a typed HTTPS or navigation action.")})
        keys = {"kind", "label", "url" if kind == "https" else "target"}
        if set(item) != keys:
            raise ValidationError({"ctas": gettext("Choose a typed HTTPS or navigation action.")})
        label = item.get("label")
        if (not isinstance(label, str) or not label.strip() or len(label) > 80
                or any(ord(char) < 32 for char in label) or any(char in label for char in "<>{}")):
            raise ValidationError({"ctas": gettext("Use a plain label of 1–80 characters.")})
        if kind == "navigation":
            if item.get("target") not in NAVIGATION_TARGETS:
                raise ValidationError({"ctas": gettext("Choose event or ticket navigation.")})
        else:
            value = item.get("url")
            if not isinstance(value, str) or len(value) > 2048:
                raise ValidationError({"ctas": gettext("Use a valid HTTPS URL.")})
            try:
                URLValidator(schemes=["https"])(value)
                parsed = urlsplit(value)
            except (DjangoValidationError, ValueError):
                raise ValidationError({"ctas": gettext("Use a valid HTTPS URL.")}) from None
            decoded = unquote(value).casefold()
            # External CTAs are public addresses. Parameters/fragments/userinfo and
            # credential-shaped paths are refused rather than persisting bearers.
            if (parsed.username or parsed.password or parsed.query or parsed.fragment
                    or any(char in decoded for char in "{}<>\\")
                    or any(ord(char) < 33 for char in decoded)
                    or re.search(r"(?:token|secret|password|credential|check-?in|invite|presign|signature)", decoded)):
                raise ValidationError({"ctas": gettext("Use a public URL without credentials or query parameters.")})
        result.append({**item, "label": label.strip()})
    return result


def pack(subject, body, *, ctas, design):
    validate_strings(subject, body, PLACEHOLDERS)
    if design not in DESIGNS:
        raise ValidationError({"design": gettext("Choose a Space Works design.")})
    # RestrictedMarkdown: paragraphs, line breaks, bullets, emphasis. Links have
    # their own typed control; scripts, HTML, images and embedded media refuse.
    if re.search(r"<[^>]*>|!\[|\]\s*\(|^\s*\[[^]]+\]:", body, flags=re.MULTILINE):
        raise ValidationError({"body": gettext("Use text and emphasis; add links as calls to action.")})
    return json.dumps({"markdown": body, "ctas": validate_ctas(ctas)}, ensure_ascii=False, separators=(",", ":"))


def unpack(campaign):
    if campaign.render_schema_version == 1:
        return {"markdown": campaign.body, "ctas": []}
    try:
        value = json.loads(campaign.body)
        if set(value) != {"markdown", "ctas"} or not isinstance(value["markdown"], str):
            raise ValueError()
        pack(campaign.subject, value["markdown"], ctas=value["ctas"], design=campaign.design)
        return value
    except (ValueError, TypeError, KeyError):
        raise ValidationError({"body": gettext("This composer payload is invalid.")}) from None


def markdown_html(value):
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", escaped)
    paragraphs = []
    for paragraph in escaped.split("\n\n"):
        lines = paragraph.splitlines()
        if lines and all(line.startswith("- ") for line in lines):
            paragraphs.append("<ul>" + "".join("<li>" + line[2:] + "</li>" for line in lines) + "</ul>")
        else:
            paragraphs.append("<p>" + paragraph.replace("\n", "<br>") + "</p>")
    return "".join(paragraphs)


def render_content(campaign, context, *, width=640, preview=False):
    payload = unpack(campaign)
    # Strings and context pass through the bounded, data-only placeholder engine.
    values = render(campaign.subject, payload["markdown"], context)
    if campaign.render_schema_version == 2:
        # The established renderer escapes template values for HTML. Decode its
        # text projection once, then escape exactly once at the HTML boundary.
        values["subject"] = html.unescape(values["subject"])
        values["text_body"] = html.unescape(values["text_body"])
    message = values["text_body"]
    links = [{"label": item["label"], "url": item.get("url") or context[
        "ticket_url" if item["target"] == "ticket" else "event_url"]} for item in payload["ctas"]]
    values["text_body"] += "".join(f"\n\n{item['label']}: {item['url']}" for item in links)
    if campaign.render_schema_version == 1:
        return values
    links_html = "".join('<p><a rel="noopener noreferrer" href="' + html.escape(item["url"], quote=True)
                         + '">' + html.escape(item["label"]) + '</a></p>' for item in links)
    from .broadcast_designs import document
    values["html_body"] = document(campaign.design, fonts=font_faces(preview=preview), width=width,
        title_html=html.escape(values["subject"]), message_html=markdown_html(message), links_html=links_html,
        organization=context.get("organization", ""),
        cover_url=cover_url(campaign) if campaign.design == "photo_header" else "")
    return values


def cover_url(campaign):
    """The event's public cover image, as the public event page shows it, or nothing."""
    event = getattr(campaign, "event", None)
    if event is None:
        return ""
    key = event.image_key
    if event.series_id and "image_key" not in (event.series_override_fields or []):
        key = event.series.image_key
    from apps.inventory import public_image_storage
    return public_image_storage.public_url(key) or ""
