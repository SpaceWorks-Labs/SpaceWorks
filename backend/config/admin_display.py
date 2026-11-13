"""How /control/ shows a value: status badges, secrets as set/not set, readable JSON, accounts by id.

Shared by every admin that wants them (``config.admin_records`` uses all four). Presentation
only: nothing here changes a stored value. Secrets are never rendered, not even masked or
truncated -- only whether one is stored. An account is shown as its id, linked to the account
page, because the account page is where personal details are masked behind an audited window.
"""

import json
import re

from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

# Field names whose value must never reach a /control/ page.
SECRET_NAME = re.compile(
    r"(secret|password|token|ciphertext|encrypted|digest|credential|private|_hash$|^hash$|api_key|"
    r"access_key|key_id|webhook_key|idempotency_key|pickup_code|checkin_token|status_secret|access_secret)"
)
JSON_LIMIT = 20000

_SUCCESS = ("paid", "succeeded", "success", "settled", "completed", "complete", "collected", "active", "confirmed",
            "approved", "accepted", "published", "verified", "ready", "registered", "attended", "ok", "won")
_WARNING = ("pending", "open", "requested", "draft", "awaiting", "processing", "submitted", "waitlist", "held",
            "hold", "partial", "unclaimed", "needs", "review", "scheduled", "queued", "running", "retrying")
_DANGER = ("failed", "failure", "cancelled", "canceled", "rejected", "lost", "disputed", "void", "expired",
           "refused", "declined", "revoked", "error", "blocked", "suspended", "closed_with_issue", "overdue")


def is_secret_name(name):
    return bool(SECRET_NAME.search(name))


def tone_for(value):
    """The badge tone for a status code: success, warning, danger or neutral."""
    text = str(value or "").lower()
    for tone, words in (("danger", _DANGER), ("success", _SUCCESS), ("warning", _WARNING)):
        if any(text == word or text.startswith(f"{word}_") or text.endswith(f"_{word}") for word in words):
            return tone
    return "neutral"


def badge(label, tone="neutral"):
    return format_html('<span class="sw-badge sw-badge--{}">{}</span>', tone, label)


def status_badge(field_name, description=None):
    """A list/detail column that shows a choice field as a coloured word (never colour alone)."""

    def display(model_admin, obj):
        value = getattr(obj, field_name, None)
        if value in (None, ""):
            return "-"
        getter = getattr(obj, f"get_{field_name}_display", None)
        return badge(getter() if callable(getter) else value, tone_for(value))

    return admin.display(description=description or _("Status"), ordering=field_name)(display)


def secret_state(obj, field_name):
    value = getattr(obj, field_name, None)
    stored = value not in (None, "", b"", {}, [])
    return badge(_("Set") if stored else _("Not set"), "success" if stored else "neutral")


def pretty_json(value):
    if value in (None, "", {}, []):
        return "-"
    text = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    if len(text) > JSON_LIMIT:
        text = text[:JSON_LIMIT] + "\n…"
    return format_html('<pre class="sw-json">{}</pre>', text)


def record_link(obj, field_name, label, route):
    """"<label> #<id>", linked to that row's /control/ page; never the row's own text."""
    row_id = getattr(obj, f"{field_name}_id", None)
    if row_id is None:
        return "-"
    text = label % {"id": row_id}
    try:
        return format_html('<a href="{}">{}</a>', reverse(route, args=[row_id]), text)
    except NoReverseMatch:
        return text


def account_link(obj, field_name):
    return record_link(obj, field_name, _("Account #%(id)s"), "admin:accounts_user_change")


def membership_link(obj, field_name):
    return record_link(obj, field_name, _("Membership #%(id)s"), "admin:makerspaces_makerspacemembership_change")
