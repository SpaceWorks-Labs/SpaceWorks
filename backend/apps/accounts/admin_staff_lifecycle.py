"""/control/ guards and the superadmin's Disable / Re-enable account actions (Q8).

Turning an account off goes through ``staff_account_lifecycle.disable_account`` (every
session and device grant revoked, every staff row revoked, audited ``account.disabled``),
behind the control step-up, so ``is_active`` is never edited directly on the form.
Space Managers no longer set staff passwords (#66): those actions are gone.
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from rest_framework.exceptions import APIException

from apps.accounts import staff_account_lifecycle as lifecycle
from apps.accounts.reauthentication import require_recent_reauth
from apps.accounts.staff_identity import is_person, person_q


class DisableAccountForm(forms.Form):
    reason = forms.CharField(min_length=3, max_length=200, widget=forms.Textarea)


class StaffLifecycleAdminMixin:
    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj)) + ("account_kind", "staff_makerspace")
        if obj is not None:
            fields += ("is_active",)
        if obj is not None and not is_person(obj):
            fields += ("is_staff", "is_superuser", "role", "access_status", "restriction_reason")
        return fields

    def has_delete_permission(self, request, obj=None):
        return bool((obj is None or is_person(obj)) and super().has_delete_permission(request, obj))

    def delete_model(self, request, obj):
        if not is_person(obj):
            raise PermissionDenied("Platform accounts and inert shells cannot be deleted.")
        return super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.exclude(person_q()).exists():
            raise PermissionDenied("Platform accounts and inert shells cannot be deleted.")
        return super().delete_queryset(request, queryset)

    def _refuse_lifecycle_bulk(self, queryset):
        """The bulk reset/restrict/restore actions act on personal accounts only; a platform
        account or inert shell in the selection refuses the whole batch (403)."""
        if queryset.exclude(person_q()).exists():
            raise PermissionDenied("Platform accounts and inert shells require their explicit lifecycle actions.")

    def _one_person(self, request, queryset):
        try:
            require_recent_reauth(request)
        except APIException as exc:
            self.message_user(request, str(getattr(exc, "detail", exc)), level=messages.ERROR)
            return None
        if queryset.count() != 1 or not is_person(queryset.first()):
            self.message_user(request, "Choose exactly one personal account.", level=messages.ERROR)
            return None
        return queryset.get()

    def _run(self, request, operation, success):
        try:
            operation()
        except APIException as exc:
            self.message_user(request, str(getattr(exc, "detail", exc)), level=messages.ERROR)
            return None
        self.message_user(request, success, level=messages.SUCCESS)
        return None

    @admin.action(description="Disable account (one person)")
    def disable_account(self, request, queryset):
        person = self._one_person(request, queryset)
        if person is None:
            return None
        if "apply" not in request.POST:
            return TemplateResponse(request, "admin/accounts/disable_account_action.html", {
                **self.admin_site.each_context(request), "title": "Disable account", "person": person,
                "opts": self.model._meta, "action_name": "disable_account",
                "action_checkbox_name": ACTION_CHECKBOX_NAME, "form": DisableAccountForm(),
            })
        form = DisableAccountForm(request.POST)
        if not form.is_valid():
            self.message_user(request, "Give a reason (3 to 200 characters).", level=messages.ERROR)
            return None
        return self._run(request, lambda: lifecycle.disable_account(
            request.user, person.pk, reason=form.cleaned_data["reason"]),
            "Account disabled. Every session has ended and its staff roles are revoked.")

    @admin.action(description="Re-enable account (one person)")
    def enable_account(self, request, queryset):
        person = self._one_person(request, queryset)
        if person is None:
            return None
        return self._run(request, lambda: lifecycle.enable_account(request.user, person.pk),
                         "Account re-enabled. Restore its staff roles per makerspace if needed.")


class ReadOnlyMembershipInlineMixin:
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
