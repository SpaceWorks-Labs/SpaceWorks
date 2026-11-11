"""/control/ "Limits & hosting": hosting type per space, request rates, billing keys and the
per-space limits page (decisions 236, 281, 284), all read-only.

Limits, quotas, hosting types and rates are set in the web console (Platform -> Spaces ->
Plans and limits, Platform settings -> Request limits), whose services re-check the
superadmin, ask for a recent sign-in on bulk changes and audit every change. These lists are
not gated on the plans switch: limits and quotas apply to every space.
"""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_safe

from config.admin_display import status_badge
from config.admin_records import ControlRecordAdmin

from .models import PlatformHostingBillingSettings
from .models_hosting_type import SpaceHostingType
from .models_throttle import PlatformThrottleRate


@admin.register(SpaceHostingType)
class SpaceHostingTypeAdmin(ControlRecordAdmin):
    list_display = ("makerspace", "type_label", "updated_at")
    list_filter = ("hosting_type",)
    search_fields = ("makerspace__name", "makerspace__slug")
    list_select_related = ("makerspace",)
    ordering = ("makerspace__name",)
    type_label = status_badge("hosting_type", _("Hosting type"))

    def get_urls(self):
        return [path("limits/", self.admin_site.admin_view(self.limits_view),
                     name="managed_hosting_spacehostingtype_limits"), *super().get_urls()]

    @method_decorator(require_safe)
    def limits_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        from config.control_limits import limits_overview

        response = TemplateResponse(request, "admin/control/limits.html", {
            **self.admin_site.each_context(request), **limits_overview(),
            "title": _("Per-space limits"), "opts": self.model._meta,
        })
        response["Cache-Control"] = "private, no-store"
        return response


@admin.register(PlatformThrottleRate)
class PlatformThrottleRateAdmin(ControlRecordAdmin):
    makerspace_lookup = None
    list_display = ("scope", "rate", "updated_at")
    search_fields = ("scope",)
    ordering = ("scope",)


@admin.register(PlatformHostingBillingSettings)
class PlatformHostingBillingSettingsAdmin(ControlRecordAdmin):
    makerspace_lookup = None
    list_display = ("id", "hosting_enabled", "auto_enforce_enabled", "provider", "grace_days",
                    "secret__stripe_secret_key", "secret__razorpay_key_secret", "updated_at")
