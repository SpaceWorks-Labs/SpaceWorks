"""Links from a makerspace's /control/ page into that space in the staff console (#115 b2).

The superadmin reads a space's reports, analytics and exports in the staff console exactly
as its Space Manager does. `?context=platform&space=<slug>` opens the platform session on
that space, so each link lands on the right tab without passing through the picker.
"""

from urllib.parse import urlencode

from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy

CONSOLE_TABS = (
    ("reports", "Reports and analytics"),
    ("dashboard", "Dashboard"),
    ("ledger", "Ledger"),
    ("data-export", "Data export"),
    ("email-log", "Email delivery log"),
    ("email-templates", "Email templates"),
    ("settings", "Settings"),
)


def console_url(space, path):
    base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{base}/admin/{path}?{urlencode({'context': 'platform', 'space': space.slug})}"


class MakerspaceConsoleLinksAdminMixin:
    """Adds a read-only "Reports and staff console" section to the change page."""

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        return fields + ("console_links",) if obj is not None else fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None:
            return fieldsets
        return (*fieldsets, ("Reports and staff console", {"fields": ("console_links",)}))

    @admin.display(description=gettext_lazy("Open in the staff console"))
    def console_links(self, obj):
        if not obj or not obj.pk or not obj.slug:
            return "Save the makerspace first."
        return format_html(
            '<ul class="flex flex-col gap-1">{}</ul>',
            format_html_join("", '<li><a href="{}" target="_blank" rel="noopener">{}</a></li>',
                             ((console_url(obj, path), label) for path, label in CONSOLE_TABS)),
        )
