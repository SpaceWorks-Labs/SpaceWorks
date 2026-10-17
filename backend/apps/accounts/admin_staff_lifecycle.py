"""Control-panel guards and explicit single-account lifecycle actions."""

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from rest_framework.exceptions import APIException

from apps.accounts import staff_account_lifecycle as lifecycle
from apps.accounts.reauthentication import require_recent_reauth


class StaffLifecycleAdminMixin:
    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj)) + ("account_kind", "staff_makerspace")
        if obj and obj.account_kind == "staff":
            fields += ("is_active", "is_staff", "is_superuser", "role", "access_status", "restriction_reason")
        return fields

    def has_delete_permission(self, request, obj=None):
        return bool((obj is None or obj.account_kind == "member")
                    and super().has_delete_permission(request, obj))

    def delete_model(self, request, obj):
        if obj.account_kind != "member":
            raise PermissionDenied("Staff and platform accounts cannot be deleted.")
        return super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        self._refuse_lifecycle_bulk(queryset)
        return super().delete_queryset(request, queryset)

    def _refuse_lifecycle_bulk(self, queryset):
        if queryset.exclude(account_kind="member").exists():
            raise PermissionDenied("Staff and platform accounts require their explicit lifecycle actions.")

    def _staff_action(self, request, queryset, operation):
        require_recent_reauth(request)
        if queryset.count() != 1:
            raise PermissionDenied("Choose exactly one staff account.")
        user = queryset.get()
        if user.account_kind != "staff":
            raise PermissionDenied("Choose a staff account.")
        try:
            result = operation(request.user, user.staff_makerspace_id, user.pk)
        except APIException as exc:
            self.message_user(request, str(exc.detail), level=messages.ERROR)
            return None
        if isinstance(result, dict):
            response = TemplateResponse(request, "admin/accounts/staff_account_result.html", {
                **self.admin_site.each_context(request), "title": "Staff password issued",
                "generated_password": result["generated_password"], "account": user,
            })
            response["Cache-Control"] = "private, no-store"
            return response
        self.message_user(request, "Staff account updated.", level=messages.SUCCESS)
        return None

    @admin.action(description="Issue an initial or replacement staff password (one account)")
    def set_staff_password(self, request, queryset):
        return self._staff_action(request, queryset,
            lambda actor, space_id, pk: lifecycle.set_password(actor, space_id, pk, generate=True))

    @admin.action(description="Deactivate staff account (one account)")
    def deactivate_staff_account(self, request, queryset):
        return self._staff_action(request, queryset, lifecycle.deactivate)

    @admin.action(description="Reactivate staff account (one account)")
    def reactivate_staff_account(self, request, queryset):
        return self._staff_action(request, queryset, lifecycle.reactivate)


class ReadOnlyMembershipInlineMixin:
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
