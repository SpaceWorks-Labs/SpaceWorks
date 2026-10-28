"""The /control/ "Security" section of a makerspace: settings, platform locks, PII window.

Every write goes through ``security_settings`` / ``pii_access`` -- the same services as
the staff API -- behind the /control/ recent re-authentication step-up. The generic
capability matrix shows ``security.*`` keys read-only; they change only here.
"""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from rest_framework.exceptions import APIException

from apps.accounts import pii_access
from apps.accounts.pii_presentation import pii_visible
from apps.accounts.reauthentication import require_recent_reauth

from . import security_settings
from .security_settings_registry import REGISTRY

ACTIONS = ("set", "lock", "unlock", "open_pii", "close_pii")


class SecurityActionForm(forms.Form):
    action = forms.ChoiceField(choices=[(name, name) for name in ACTIONS])
    key = forms.ChoiceField(choices=[(setting.key, setting.label) for setting in REGISTRY], required=False)
    enabled = forms.BooleanField(required=False)
    note = forms.CharField(max_length=200, required=False)
    reason = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))


def _describe(row):
    value = "On" if row["value"] is True else "Off" if row["value"] is False else row["value"]
    if row["lock"] is None:
        return f"{row['label']}: {value}"
    note = f" ({row['lock']['note']})" if row["lock"]["note"] else ""
    return f"{row['label']}: {value} - locked by platform at {row['lock']['floor']}{note}"


class MakerspaceSecurityAdminMixin:
    def get_urls(self):
        return [path("<int:object_id>/security/", self.admin_site.admin_view(self.security_view),
                     name="makerspaces_makerspace_security"), *super().get_urls()]

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj is not None and obj.pk:
            fieldsets.append(("Security", {"fields": ("security_settings_summary",)}))
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), "security_settings_summary")

    @admin.display(description="Security settings")
    def security_settings_summary(self, obj):
        if not obj or not obj.pk:
            return "Save this makerspace first."
        rows = format_html_join("", "<li>{}</li>", ((_describe(row),) for row in security_settings.effective(obj)))
        url = reverse("admin:makerspaces_makerspace_security", args=[obj.pk])
        return format_html('<ul>{}</ul><a href="{}">Manage security and PII access</a>', rows, url)

    def security_view(self, request, object_id):
        space = self.get_object(request, str(object_id))
        if space is None or not self.has_view_permission(request, space):
            raise PermissionDenied()
        if request.method == "POST":
            from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
            response = RecentReauthenticationAdminMixin()._recent_redirect(request)
            if response is not None:
                return response
            require_recent_reauth(request)
            form = SecurityActionForm(request.POST)
            if form.is_valid():
                try:
                    self._apply_security_action(request, space, form.cleaned_data)
                except (ValidationError, APIException) as exc:
                    detail = getattr(exc, "detail", None)
                    text = detail.get("detail") if isinstance(detail, dict) else (detail or "; ".join(exc.messages))
                    self.message_user(request, str(text), messages.ERROR)
                else:
                    self.message_user(request, "Saved.", messages.SUCCESS)
            else:
                self.message_user(request, "Check the form and try again.", messages.ERROR)
            return redirect(reverse("admin:makerspaces_makerspace_security", args=[space.pk]))
        pii_access.sweep_expired(makerspace_id=space.pk)
        return TemplateResponse(request, "admin/makerspaces/security_settings.html", {
            **self.admin_site.each_context(request), "title": f"Security at {space.name}", "space": space,
            "settings": security_settings.effective(space), "pii_visible": pii_visible(request.user, space.pk),
            "own_window": pii_access.active_grants(request.user).filter(makerspace=space).first(),
            "opts": self.model._meta,
        })

    def _apply_security_action(self, request, space, data):
        action, key, actor = data["action"], data["key"], request.user
        if action in {"set", "lock", "unlock"} and not key:
            raise ValidationError("Choose a setting.")
        if action == "set":
            security_settings.set_setting(actor, space, key, data["enabled"], via=security_settings.PLATFORM)
        elif action == "lock":
            security_settings.lock(actor, space, key, True, data["note"])
        elif action == "unlock":
            security_settings.unlock(actor, space, key)
        elif action == "open_pii":
            pii_access.open_grant(actor, space, data["reason"])
        else:
            grant = pii_access.active_grants(actor).filter(makerspace=space).first()
            if grant is None:
                raise ValidationError("No PII access window is open here.")
            pii_access.close_grant(actor, grant)
