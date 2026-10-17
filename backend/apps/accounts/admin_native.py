from django.contrib import admin
from unfold.admin import ModelAdmin
from apps.accounts.models import NativeAppRegistration
from config.admin_access import SuperuserOnlyModelAdmin


@admin.register(NativeAppRegistration)
class NativeAppRegistrationAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = (
        "app_id", "platform", "environment", "makerspace", "status", "updated_at",
    )
    list_filter = ("status", "platform", "environment", "makerspace")
    search_fields = ("app_id", "verifier_config_key", "makerspace__name")
    autocomplete_fields = ("makerspace", "approved_by")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        """Route a revocation through the service so live grants are settled too.

        Saving `status = revoked` on the row alone would leave existing grants and refresh
        tokens intact, so re-approving later would resurrect them.
        """
        becoming_revoked = (
            obj.status == NativeAppRegistration.Status.REVOKED
            and (not change or "status" in (form.changed_data or []))
        )
        super().save_model(request, obj, form, change)
        if becoming_revoked:
            from apps.accounts.services_native_apps import revoke_registration

            revoke_registration(obj, actor=request.user)

