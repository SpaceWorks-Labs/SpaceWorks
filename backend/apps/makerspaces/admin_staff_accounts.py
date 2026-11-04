"""Invite staff to a makerspace from /control/ through exactly the staff-roles service.

One account per person: /control/ no longer creates staff accounts. It sends the same
email invitation as ``POST admin/makerspaces/<id>/staff-roles/``; the invitee accepts it
while signed in to their own account. Granting to an existing member is done from the
staff console (the superadmin reaches it for every space). The method and URL names
are kept so the makerspace admin keeps its link.
"""

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from rest_framework.exceptions import APIException

from apps.accounts.reauthentication import require_recent_reauth
from apps.accounts.services_staff_invitations import issue
from apps.accounts.staff_account_policy import require_authority
from apps.accounts.staff_invitation_delivery import deliver


class CreateStaffAccountForm(forms.Form):
    email = forms.EmailField()
    roles = forms.MultipleChoiceField()
    machine_type_ids = forms.TypedMultipleChoiceField(coerce=int, required=False)

    def __init__(self, space, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.machines.member_scope_services import assignable_machine_types
        self.fields["roles"].choices = list(space.roles.exclude(slug="member").values_list("slug", "name"))
        self.fields["machine_type_ids"].choices = list(assignable_machine_types(space).values_list("pk", "name"))


class MakerspaceStaffAccountAdminMixin:
    def get_urls(self):
        return [path("<int:object_id>/staff-account/create/", self.admin_site.admin_view(self.create_staff_account_view),
                     name="makerspaces_makerspace_create_staff_account"), *super().get_urls()]

    @admin.display(description="Staff")
    def create_staff_account_link(self, obj):
        if not obj or not obj.pk:
            return "Save this makerspace first."
        return format_html('<a href="{}">Invite staff by email</a>', reverse(
            "admin:makerspaces_makerspace_create_staff_account", args=[obj.pk]))

    def create_staff_account_view(self, request, object_id):
        space = self.get_object(request, str(object_id))
        if space is None or not self.has_change_permission(request, space):
            raise PermissionDenied()
        try:
            require_authority(request.user, space)
        except APIException as exc:
            raise PermissionDenied() from exc
        form = CreateStaffAccountForm(space, request.POST or None)
        if request.method == "POST":
            from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
            response = RecentReauthenticationAdminMixin()._recent_redirect(request)
            if response is not None:
                return response
            require_recent_reauth(request)
            if form.is_valid():
                try:
                    row, raw = issue(request.user, space.pk, **form.cleaned_data)
                except APIException as exc:
                    form.add_error(None, str(exc.detail))
                else:
                    deliver(row, raw)
                    self.message_user(request, "Invitation sent. The person accepts it while signed in to "
                                               "their own account with that email.")
                    return redirect(reverse("admin:makerspaces_makerspace_change", args=[space.pk]))
        return TemplateResponse(request, "admin/accounts/staff_account_form.html", {
            **self.admin_site.each_context(request), "title": f"Invite staff to {space.name}", "form": form,
        })
