"""The /control/ "Keys" page of a makerspace: rotation, emergency re-key, search key, browser key.

Superadmin only (every admin model is). Each POST passes the /control/ recent
re-authentication step-up and calls the same services the background jobs finish. Every
action is audited in the space, so its managers see it in ``security/key-events``.
"""

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from apps.accounts.reauthentication import require_recent_reauth
from django.utils.translation import gettext_lazy
from django.utils.translation import gettext

ACTIONS = ("rotate_dek", "emergency_rekey", "rotate_search_key", "rotate_publishable_key")


class MakerspaceKeysAdminMixin:
    def get_urls(self):
        return [path("<int:object_id>/keys/", self.admin_site.admin_view(self.keys_view),
                     name="makerspaces_makerspace_keys"), *super().get_urls()]

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj is not None and obj.pk:
            fieldsets.append(("Encryption keys", {"fields": ("encryption_keys_summary",)}))
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), "encryption_keys_summary")

    @admin.display(description=gettext_lazy("Encryption keys"))
    def encryption_keys_summary(self, obj):
        if not obj or not obj.pk:
            return "Save this makerspace first."
        from .key_events import key_state
        state = key_state(obj)
        url = reverse("admin:makerspaces_makerspace_keys", args=[obj.pk])
        return format_html('Data key version {} - search key {} <a href="{}">Rotate or re-key</a>',
                           state["active_dek_version"] or "none", state["search_key_version"] or "deployment", url)

    def keys_view(self, request, object_id):
        space = self.get_object(request, str(object_id))
        if space is None or not self.has_view_permission(request, space):
            raise PermissionDenied()
        if request.method == "POST":
            from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
            response = RecentReauthenticationAdminMixin()._recent_redirect(request)
            if response is not None:
                return response
            require_recent_reauth(request)
            try:
                text = self._apply_key_action(request, space, request.POST.get("action", ""))
            except ValidationError as exc:
                self.message_user(request, "; ".join(exc.messages), messages.ERROR)
            else:
                self.message_user(request, text, messages.SUCCESS)
            return redirect(reverse("admin:makerspaces_makerspace_keys", args=[space.pk]))
        from apps.tenant_rls.role_contract import status
        from .key_events import key_state
        rls = status()
        if rls["mode"] != "enforce":
            self.message_user(request, f"Row-level security is {rls['mode']} on this deployment: the database "
                                       "does not yet stop a cross-space read. See Control > Row-level security.",
                              messages.WARNING)
        return TemplateResponse(request, "admin/encryption/makerspace_keys.html", {
            **self.admin_site.each_context(request), "title": f"Encryption keys of {space.name}",
            "space": space, "state": key_state(space), "opts": self.model._meta,
        })

    def _apply_key_action(self, request, space, action):
        from . import publishable_keys, rotation
        if action not in ACTIONS:
            raise ValidationError(gettext("Choose an action."))
        if action in {"rotate_dek", "emergency_rekey"}:
            job = rotation.start_dek_rotation(request.user, space, emergency=action == "emergency_rekey")
            return f"Key version {job.to_version} is now in use; older records are re-encrypted in the background."
        if action == "rotate_search_key":
            job = rotation.start_search_key_rotation(request.user, space)
            return f"Search key version {job.to_version} is in use; the space is re-indexed in the background."
        _key, valid_until = publishable_keys.rotate_publishable_key(request.user, space)
        return f"New browser key issued. The previous key works until {valid_until:%Y-%m-%d %H:%M} UTC."
