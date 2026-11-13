"""The ``/control/`` user action that resets one person's two-step sign-in (superadmin).

Behind the control step-up (``require_recent_reauth`` on the control session) and a
reason form; the service applies the superadmin rule and audits ``auth.mfa_reset``.
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.template.response import TemplateResponse
from rest_framework.exceptions import APIException

from apps.accounts import mfa_reset
from apps.accounts.reauthentication import require_recent_reauth
from django.utils.translation import gettext_lazy


class MfaResetForm(forms.Form):
    reason = forms.CharField(min_length=3, max_length=300, widget=forms.Textarea)


class MfaResetAdminMixin:
    @admin.action(description=gettext_lazy("Reset two-step sign-in (one person)"))
    def reset_two_step(self, request, queryset):
        try:
            require_recent_reauth(request)
        except APIException as exc:
            self.message_user(request, str(getattr(exc, "detail", exc)), level=messages.ERROR)
            return None
        if queryset.count() != 1:
            self.message_user(request, "Choose exactly one person.", level=messages.ERROR)
            return None
        person = queryset.get()
        if "apply" not in request.POST:
            return TemplateResponse(request, "admin/accounts/mfa_reset_action.html", {
                **self.admin_site.each_context(request), "title": "Reset two-step sign-in",
                "person": person, "opts": self.model._meta, "action_name": "reset_two_step",
                "action_checkbox_name": ACTION_CHECKBOX_NAME, "form": MfaResetForm(),
            })
        form = MfaResetForm(request.POST)
        if not form.is_valid():
            self.message_user(request, "Give a reason (3 to 300 characters).", level=messages.ERROR)
            return None
        try:
            mfa_reset.reset(request.user, person, form.cleaned_data["reason"])
        except APIException as exc:
            self.message_user(request, str(getattr(exc, "detail", exc)), level=messages.ERROR)
            return None
        self.message_user(request, "Two-step sign-in reset. Every session of that person has ended.",
                          level=messages.SUCCESS)
        return None
