from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path
from django.views.decorators.http import require_safe
from django.utils.decorators import method_decorator
from unfold.admin import ModelAdmin

from apps.accounts.forms_native_apps import NativeAppRegistrationForm
from apps.accounts.mobile_readiness import mobile_readiness
from apps.accounts.models_devices import NativeAppRegistration
from config.admin_access import SuperuserOnlyModelAdmin
from config.admin_audit import AuditedControlChangeMixin


@admin.register(NativeAppRegistration)
class NativeAppRegistrationAdmin(AuditedControlChangeMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    audit_action = "native_app.registration_updated"
    form = NativeAppRegistrationForm
    change_list_template = "admin/accounts/nativeappregistration/change_list.html"
    list_display = ("app_id", "platform", "environment", "makerspace", "status", "updated_at")
    list_filter = ("status", "platform", "environment", "makerspace")
    search_fields = ("app_id", "verifier_config_key", "makerspace__name")
    autocomplete_fields = ("makerspace", "approved_by")
    readonly_fields = ("created_at", "updated_at")

    def get_urls(self):
        return [path("mobile-readiness/", self.admin_site.admin_view(self.readiness_view),
                     name="accounts_nativeappregistration_mobile_readiness"), *super().get_urls()]

    @method_decorator(require_safe)
    def readiness_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        response = TemplateResponse(request, "admin/mobile_readiness.html", {
            **self.admin_site.each_context(request), **mobile_readiness(),
            "title": "Mobile integration readiness", "opts": self.model._meta,
        })
        response["Cache-Control"] = "private, no-store"
        return response

    def has_delete_permission(self, request, obj=None):
        # Revocation settles live grants and preserves their registration/audit trail.
        return False

    def save_model(self, request, obj, form, change):
        becoming_revoked = (
            obj.status == NativeAppRegistration.Status.REVOKED
            and (not change or "status" in (form.changed_data or []))
        )
        super().save_model(request, obj, form, change)
        if becoming_revoked:
            from apps.accounts.services_native_apps import revoke_registration
            revoke_registration(obj, actor=request.user)
