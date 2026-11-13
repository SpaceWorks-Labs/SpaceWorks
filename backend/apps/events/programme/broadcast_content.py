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
from .broadcast_markdown import markdown_html, plain_text, validate_markdown

PLACEHOLDERS = ("name", "event_title", "event_date", "event_location", "ticket_url",
                "event_url", "feedback_url", "schedule_url", "organization")
NAVIGATION_TARGETS = ("event", "ticket")
# (family, file, weight range): Outfit (OFL) carries text, free Gilroy ExtraBold the headings.
EMAIL_FACES = (("Outfit", "Outfit-Variable", "400 700"), ("Gilroy", "Gilroy-ExtraBold", "800"))


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
    return "".join('@font-face{font-family:"' + family + '";src:url("' + origin + '/fonts/' + face
        + '.woff2") format("woff2");font-style:normal;font-weight:' + weight
        + ';font-display:swap;}' for family, face, weight in EMAIL_FACES)


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
    # Safe markdown subset (broadcast_markdown): headings, quotes, lists, emphasis and https/mailto
    # links. Scripts, HTML, images and every other scheme refuse; buttons keep their typed CTA control.
    validate_markdown(body)
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


URL_PLACEHOLDERS = ("ticket_url", "event_url", "feedback_url", "schedule_url")


def _link_safe(context):
    """Free-text values (names, titles) cannot smuggle link syntax into a body; URL values pass through."""
    return {key: value if key in URL_PLACEHOLDERS or not isinstance(value, str)
            else value.replace("[", "(").replace("]", ")") for key, value in context.items()}


def render_content(campaign, context, *, width=640, preview=False):
    payload = unpack(campaign)
    # Strings and context pass through the bounded, data-only placeholder engine.
    values = render(campaign.subject, payload["markdown"], _link_safe(context))
    if campaign.render_schema_version == 2:
        # The established renderer escapes template values for HTML. Decode its
        # text projection once, then escape exactly once at the HTML boundary.
        values["subject"] = html.unescape(values["subject"])
        values["text_body"] = html.unescape(values["text_body"])
    message = values["text_body"]
    if campaign.render_schema_version == 2:
        values["text_body"] = plain_text(message)
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
