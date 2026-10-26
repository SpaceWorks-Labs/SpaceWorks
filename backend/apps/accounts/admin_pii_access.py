"""/control/ pages for superadmin PII windows (owner decision #111 Q12).

- "Platform PII access grants": the read-only history of every window, with an action to
  close your own open ones. Space windows are opened from a makerspace's Security page.
- The per-person reveal on a user's page: a masked person can be revealed for 30 minutes
  with a reason and the /control/ step-up; it is audited in every space they belong to.
"""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from rest_framework.exceptions import APIException
from unfold.admin import ModelAdmin

from apps.accounts import pii_access
from apps.accounts.models_pii_access import PlatformPiiAccessGrant
from apps.accounts.pii_presentation import person_pii_visible
from apps.accounts.platform_authority import is_platform_superadmin
from apps.accounts.reauthentication import require_recent_reauth
from config.admin_access import SuperuserOnlyModelAdmin


class PiiReasonForm(forms.Form):
    reason = forms.CharField(min_length=10, max_length=300, widget=forms.Textarea(attrs={"rows": 3}),
                             help_text="Why you need to see this person's details. Their spaces' managers can read it.")


def _error_text(exc):
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        return str(detail.get("detail", detail))
    return str(detail) if detail is not None else "; ".join(getattr(exc, "messages", [str(exc)]))


class PersonPiiRevealAdminMixin:
    """Adds the per-person reveal to the user admin; pairs with PiiMaskingAdminMixin."""

    def get_urls(self):
        return [path("<int:object_id>/pii-reveal/", self.admin_site.admin_view(self.pii_reveal_view),
                     name="accounts_user_pii_reveal"), *super().get_urls()]

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj is not None and is_platform_superadmin(request.user) and not person_pii_visible(request.user, obj):
            fieldsets.insert(0, ("Personal data", {"fields": ("pii_reveal_link",)}))
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), "pii_reveal_link")

    @admin.display(description="Personal data")
    def pii_reveal_link(self, obj):
        if not obj or not obj.pk:
            return "-"
        return format_html('Masked. <a href="{}">Reveal for 30 minutes</a>',
                           reverse("admin:accounts_user_pii_reveal", args=[obj.pk]))

    def pii_reveal_view(self, request, object_id):
        person = self.get_object(request, str(object_id))
        if person is None or not self.has_view_permission(request, person) or not is_platform_superadmin(request.user):
            raise PermissionDenied()
        form = PiiReasonForm(request.POST or None)
        if request.method == "POST":
            from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
            response = RecentReauthenticationAdminMixin()._recent_redirect(request)
            if response is not None:
                return response
            require_recent_reauth(request)
            if form.is_valid():
                try:
                    pii_access.open_person_grant(request.user, person, form.cleaned_data["reason"])
                except (ValidationError, APIException) as exc:
                    form.add_error(None, _error_text(exc))
                else:
                    self.message_user(request, "Personal data is visible for 30 minutes. The reveal is "
                                      "recorded in every space this person belongs to.", messages.SUCCESS)
                    return redirect(reverse("admin:accounts_user_change", args=[person.pk]))
        return TemplateResponse(request, "admin/accounts/pii_reason_form.html", {
            **self.admin_site.each_context(request), "title": f"Reveal personal data of {person.username}",
            "form": form, "opts": self.model._meta,
        })


@admin.register(PlatformPiiAccessGrant)
class PlatformPiiAccessGrantAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("opened_at", "actor", "makerspace", "subject_account", "reason", "expires_at", "closed_at",
                    "close_reason")
    list_filter = ("close_reason",)
    readonly_fields = ("actor", "makerspace", "subject_account", "reason", "opened_at", "expires_at", "closed_at",
                       "close_reason")
    fields = readonly_fields
    actions = ["close_own_windows"]

    @admin.display(description="Person")
    def subject_account(self, obj):
        return obj.subject.username if obj.subject_id else "-"

    def get_queryset(self, request):
        pii_access.sweep_expired()
        return super().get_queryset(request).select_related("actor", "makerspace", "subject")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Close my selected open windows")
    def close_own_windows(self, request, queryset):
        closed = 0
        for grant in queryset.filter(actor=request.user, closed_at__isnull=True):
            pii_access.close_grant(request.user, grant)
            closed += 1
        self.message_user(request, f"Closed {closed} window(s).", messages.SUCCESS)
