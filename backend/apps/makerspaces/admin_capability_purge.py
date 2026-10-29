"""The /control/ "Purge <capability> data" action (#128 C-8, #97).

Switching a folded capability off (maintenance, To-Buy, warranty, per parent) keeps its
data. Deleting it is this separate superadmin action: the page previews exactly what each
capability would lose, and the POST needs a recent re-authentication, the switch to be
off already, and the capability key typed back as confirmation. Every purge is audited in
the space's own log by `capability_purge`.
"""

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from apps.accounts.reauthentication import require_recent_reauth

from . import capability_purge

_URL_NAME = "makerspaces_makerspace_capability_purge"


class MakerspaceCapabilityPurgeAdminMixin:
    def get_urls(self):
        return [path("<int:object_id>/capability-purge/", self.admin_site.admin_view(self.capability_purge_view),
                     name=_URL_NAME), *super().get_urls()]

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj is not None and obj.pk:
            fieldsets.append(("Capability data", {"fields": ("capability_purge_link",)}))
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), "capability_purge_link")

    @admin.display(description="Purge capability data")
    def capability_purge_link(self, obj):
        if not obj or not obj.pk:
            return "Save this makerspace first."
        return format_html('<a href="{}">Preview and purge switched-off maintenance, To-Buy or warranty data</a>',
                           reverse(f"admin:{_URL_NAME}", args=[obj.pk]))

    def capability_purge_view(self, request, object_id):
        space = self.get_object(request, str(object_id))
        if space is None or not self.has_view_permission(request, space):
            raise PermissionDenied()
        if request.method == "POST":
            from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
            response = RecentReauthenticationAdminMixin()._recent_redirect(request)
            if response is not None:
                return response
            require_recent_reauth(request)
            key, confirm = request.POST.get("key", ""), request.POST.get("confirm", "")
            try:
                if not key or confirm.strip() != key:
                    raise ValidationError("Type the capability key exactly to confirm the purge.")
                counts = capability_purge.purge_capability(space, key, request.user)
            except ValidationError as exc:
                self.message_user(request, "; ".join(exc.messages), messages.ERROR)
            else:
                summary = ", ".join(f"{name}: {count}" for name, count in counts.items()) or "nothing"
                self.message_user(request, f"Purged {key} data ({summary}).", messages.SUCCESS)
            return redirect(reverse(f"admin:{_URL_NAME}", args=[space.pk]))
        return TemplateResponse(request, "admin/makerspaces/capability_purge.html", {
            **self.admin_site.each_context(request), "title": f"Capability data at {space.name}",
            "space": space, "plans": capability_purge.purgeable_capabilities(space), "opts": self.model._meta,
        })
